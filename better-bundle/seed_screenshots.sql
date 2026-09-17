-- ============================================================
-- Seed data for BetterBundle listing screenshots.
--
--   docker exec -i betterbundle-postgres-dev psql -U postgres -d betterbundle \
--     -f /dev/stdin < better-bundle/seed_screenshots.sql
--
-- Everything here is generated from ONE set of shoppers, so the three pages a
-- merchant looks at cannot contradict each other:
--
--   Overview  per-placement Shown / Accepted / Revenue, and the cycle card
--   Proof     treatment-vs-holdout incrementality
--   Billing   trial completion, cycle usage, the cap
--
-- The previous version drew each of those from independent random(), which is
-- why the dashboard showed 42 accepted post-purchase offers worth nothing and
-- an `attributed_revenue` whose own "total" key disagreed with `total_revenue`
-- on the same row. A screenshot of numbers that cannot all be true at once is
-- worse than no screenshot.
--
-- The chain, in one direction:
--
--   shopper -> impression(s) -> (some convert) order
--                            -> (some of those) accepted impression
--                            -> purchase_attribution -> commission_record
--
-- Every derived figure is an aggregate of the step above it. Nothing is
-- invented twice.
--
-- SAFE TO RE-RUN. Deletes only rows matching the seed's own id patterns, so the
-- real Shopify data in this database (997 products, 161 orders, 12 live
-- impressions at the time of writing) is left alone.
-- ============================================================

DO $$
DECLARE
  -- ---- knobs. Everything below is derived from these. -------------------
  c_days            INT     := 30;      -- window the store's history spans
  c_shoppers        INT     := 12000;   -- randomised shoppers in the window
  c_holdout         INT     := 10;      -- % held out, matches INITIAL_HOLDOUT_PERCENT

  -- Conversion rates for the two arms. The gap is the whole point of the Proof
  -- page, and it has to clear two bars at once: MIN_CONTROL_ORDERS = 100
  -- control *converters* before any number is reported, and p < 0.05 on the
  -- two-proportion z-test. 1200 control shoppers at 10% gives 120 converters,
  -- and 12.5% vs 10% over 10800/1200 lands near p = 0.017.
  --
  -- Lower either rate, or c_shoppers, and the Proof page correctly falls back
  -- to "insufficient data" — that is the engine working, not a seeding bug.
  c_conv_treat      NUMERIC := 0.125;
  c_conv_ctrl       NUMERIC := 0.10;

  -- A small basket-size difference on top of the conversion difference. Keep it
  -- small: lift is measured on the shopper's WHOLE order, not on the
  -- recommended line, so every dollar of AOV gap is multiplied by 10,800
  -- treatment shoppers and lands in incremental revenue.
  c_aov_treat       NUMERIC := 116.00;
  c_aov_ctrl        NUMERIC := 112.00;

  -- Share of treatment orders where a recommendation was actually accepted,
  -- and how much of such an order the accepted offer accounts for. These two
  -- alone decide attributed revenue, and therefore the entire billing page.
  --
  -- They also have to keep ATTRIBUTED above INCREMENTAL. Attribution credits a
  -- whole accepted offer to the app; incrementality only credits the difference
  -- against the holdout, so attribution is the upper bound and incrementality
  -- is the honest subset — see the docstring at the top of lift_service.py.
  -- A seed where Proof claims more than billing ever attributed would have the
  -- app contradicting its own explanation of the two numbers, on the listing.
  c_influenced      NUMERIC := 0.60;
  c_attr_share      NUMERIC := 0.45;

  -- Read from subscription_plans below; these are only the fallbacks.
  c_rate            NUMERIC := 0.03;
  c_cap             NUMERIC := 29.00;
  c_trial_threshold NUMERIC := 1000.00;

  v_shop_id      VARCHAR;
  v_sub_id       VARCHAR;
  v_cycle_id     VARCHAR;
  v_start        TIMESTAMPTZ := now() - (30 * interval '1 day');
  v_trial_end    TIMESTAMPTZ;
  v_impressions  INT;
  v_orders       INT;
  v_ctrl_conv    INT;
  v_attributed   NUMERIC;

  v_product_ids VARCHAR[] := ARRAY[
    'gid://shopify/Product/9001','gid://shopify/Product/9002','gid://shopify/Product/9003',
    'gid://shopify/Product/9004','gid://shopify/Product/9005','gid://shopify/Product/9006',
    'gid://shopify/Product/9007','gid://shopify/Product/9008','gid://shopify/Product/9009',
    'gid://shopify/Product/9010'
  ];
  v_titles TEXT[] := ARRAY[
    'Graphic Dress','Floral Sleeveless Dress','Buttercup Dress',
    'Paper Dress','3/4 Sleeve Kimono Dress','Eulera Leather Skirt',
    'Easy Slim Pant','Float Bead Earring','Canvas Tote Bag','Leather Crossbody Bag'
  ];
  v_prices FLOAT[] := ARRAY[523.60,383.60,418.60,488.60,551.60,607.60,158.00,58.00,89.99,129.99];

  -- Checkout (mercury) is deliberately absent: it is Shopify Plus only, and a
  -- non-Plus dev store showing checkout traffic would be a lie on the listing.
  -- It renders as "Awaiting traffic", which is the honest state.
  v_surfaces TEXT[] := ARRAY['phoenix','apollo','thank_you','venus'];
BEGIN
  -- Reproducible: the same seed produces the same screenshots.
  PERFORM setseed(0.42);

  SELECT id INTO v_shop_id FROM shops LIMIT 1;
  IF v_shop_id IS NULL THEN RAISE EXCEPTION 'No shop found'; END IF;

  SELECT id INTO v_sub_id FROM shop_subscriptions
   WHERE shop_id = v_shop_id AND is_active = true LIMIT 1;
  IF v_sub_id IS NULL THEN
    RAISE EXCEPTION 'No active subscription for shop %. Install the app first.', v_shop_id;
  END IF;

  SELECT COALESCE(s.commission_rate_override, p.commission_rate, c_rate),
         COALESCE(s.cap_amount_override, p.cap_amount, c_cap),
         COALESCE(s.trial_threshold_override, p.trial_revenue_threshold, c_trial_threshold)
    INTO c_rate, c_cap, c_trial_threshold
    FROM shop_subscriptions s
    LEFT JOIN subscription_plans p ON p.id = s.subscription_plan_id
   WHERE s.id = v_sub_id;

  RAISE NOTICE 'Shop % / subscription % (rate %, cap %, trial threshold %)',
    v_shop_id, v_sub_id, c_rate, c_cap, c_trial_threshold;

  -- ---- clean previous seed, and only previous seed ----------------------
  -- Every pattern here is one the seeder itself writes. Real Shopify ids are
  -- numeric or gid:// with high numbers, so none of them can match.
  DELETE FROM commission_records    WHERE shop_id = v_shop_id AND order_id LIKE 'ord-%';
  DELETE FROM purchase_attributions WHERE shop_id = v_shop_id AND order_id LIKE 'ord-%';
  -- 'sess-%' is the pattern the pre-rewrite seeder used. Without it those rows
  -- survive, and they carry their own `paid` revenue — which lands in the
  -- Overview accept counts and top-products list while matching no attribution,
  -- reproducing exactly the "accepted offers worth nothing" symptom this
  -- rewrite exists to remove. Real impressions carry a Shopify session id and
  -- match neither pattern.
  DELETE FROM offer_impressions     WHERE shop_id = v_shop_id
                                      AND (session_id LIKE 'seed-%' OR session_id LIKE 'sess-%');
  -- 'so-%' is the pre-rewrite seeder's order pattern. It has to go for the same
  -- reason as 'sess-%': those orders carry customer ids in the same 'cust-N'
  -- space this seeder mints, so lift_service joins them onto the new shoppers
  -- and credits a treatment shopper with an order they never placed. That alone
  -- pushed treatment AOV from $119 to $132 and inflated incremental revenue by
  -- roughly $17k. Real Shopify order ids are numeric and match neither pattern.
  DELETE FROM line_item_data        WHERE order_id IN (
    SELECT id FROM order_data WHERE shop_id = v_shop_id
      AND (order_id LIKE 'ord-%' OR order_id LIKE 'so-%'));
  DELETE FROM order_data            WHERE shop_id = v_shop_id
                                      AND (order_id LIKE 'ord-%' OR order_id LIKE 'so-%');
  DELETE FROM customer_data         WHERE shop_id = v_shop_id AND customer_id LIKE 'cust-%';
  DELETE FROM product_edges         WHERE shop_id = v_shop_id AND source_product_id LIKE 'gid://shopify/Product/90%';
  DELETE FROM product_data          WHERE shop_id = v_shop_id AND product_id LIKE 'gid://shopify/Product/90%';
  -- Every cycle this subscription has ever had came from a seeder; the shop has
  -- never been billed for real. Scoped to the subscription so another shop in
  -- the same database is untouched.
  DELETE FROM billing_cycles        WHERE shop_subscription_id = v_sub_id;
  RAISE NOTICE 'Cleared previous seed';

  -- ---- catalogue --------------------------------------------------------
  INSERT INTO product_data (id,product_id,title,handle,product_type,vendor,status,total_inventory,price,compare_at_price,is_active,shop_id,created_at,updated_at,images)
  SELECT gen_random_uuid()::varchar, v_product_ids[i], v_titles[i],
         replace(lower(v_titles[i]),' ','-'), 'Clothing', 'Demo Store', 'active',
         (12 + (i * 7) % 40), v_prices[i], (v_prices[i] * 1.2)::float, true, v_shop_id,
         v_start - interval '30 days', now(),
         json_build_array(json_build_object(
           'url','https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400',
           'alt', v_titles[i]))
    FROM generate_series(1,10) i
  ON CONFLICT DO NOTHING;

  INSERT INTO product_edges (shop_id,source_product_id,target_product_id,edge_type,prior_score,observed_count,observed_llr,blended_score,prior_reason,created_at,updated_at)
  SELECT v_shop_id, v_product_ids[i], v_product_ids[i+1], 'cross_sell',
         round((0.30 + random()*0.50)::numeric, 3)::float,
         (5 + (i*11) % 30), round((0.5 + random()*2)::numeric, 3)::float,
         round((0.20 + random()*0.70)::numeric, 3)::float,
         'Co-purchase pattern', v_start, now()
    FROM generate_series(1,8) i
  ON CONFLICT DO NOTHING;

  -- ---- the shoppers everything else derives from ------------------------
  -- One row per randomised shopper, which is the unit lift_service analyses.
  -- Held out by id so the arm is stable across re-runs.
  CREATE TEMP TABLE seed_shopper ON COMMIT DROP AS
  SELECT 'cust-' || g                                   AS customer_id,
         (g % (100 / c_holdout)) = 0                    AS is_control,
         v_start + (random() * c_days) * interval '1 day' AS seen_at
    FROM generate_series(1, c_shoppers) g;

  -- ---- who bought -------------------------------------------------------
  -- Exactly ceil(arm * rate) per arm rather than a coin flip per shopper: the
  -- Proof page has a hard MIN_CONTROL_ORDERS = 100 gate, and a binomial draw
  -- around 120 can land under it and silently turn the page into an empty
  -- state on a re-run. Ordered by md5 so the choice is arbitrary but fixed.
  CREATE TEMP TABLE seed_order ON COMMIT DROP AS
  WITH ranked AS (
    SELECT s.*,
           row_number() OVER (PARTITION BY is_control ORDER BY md5(customer_id)) AS rn,
           count(*)     OVER (PARTITION BY is_control)                           AS arm_n
      FROM seed_shopper s
  ), picked AS (
    SELECT customer_id, is_control, seen_at
      FROM ranked
     WHERE rn <= CEIL(arm_n * CASE WHEN is_control THEN c_conv_ctrl ELSE c_conv_treat END)
  )
  SELECT customer_id,
         is_control,
         'ord-' || row_number() OVER (ORDER BY seen_at, customer_id) AS order_id,
         seen_at + (random() * 6) * interval '1 hour'                AS order_date,
         round(((CASE WHEN is_control THEN c_aov_ctrl ELSE c_aov_treat END)
                * (0.45 + random() * 1.15))::numeric, 2)             AS total_amount
    FROM picked;

  -- ---- which of those a recommendation actually contributed to ----------
  -- Treatment only. A held-out shopper was shown no offer, so an accepted
  -- impression on their order would be a bug rather than revenue.
  CREATE TEMP TABLE seed_influenced ON COMMIT DROP AS
  WITH ranked AS (
    SELECT o.*,
           row_number() OVER (ORDER BY md5(o.order_id)) AS rn,
           count(*)     OVER ()                         AS n
      FROM seed_order o
     WHERE NOT o.is_control
  )
  SELECT customer_id, order_id, order_date, total_amount,
         round(total_amount * c_attr_share, 2) AS attributed,
         -- Half the influenced orders accepted two offers. Exercises the
         -- per-placement summing in the attribution engine: a dict keyed by
         -- placement has to add these, not overwrite one with the other.
         CASE WHEN rn % 2 = 0 THEN 2 ELSE 1 END AS n_accepted
    FROM ranked
   WHERE rn <= CEIL(n * c_influenced);

  -- ---- impressions ------------------------------------------------------
  -- Every shopper saw 1-3 offers. `metadata.bucketed` is what lift_service
  -- reads to decide a shopper could have been randomised at all; without it
  -- they are excluded from both arms.
  INSERT INTO offer_impressions
    (id,shop_id,session_id,customer_id,surface,offer_type,offer_id,variant_id,
     is_control,outcome,outcome_at,revenue_added,paid,metadata,impression_group_id,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, v_shop_id,
         'seed-' || s.customer_id, s.customer_id,
         v_surfaces[1 + (abs(hashtext(s.customer_id || k::text)) % 4)],
         'product',
         v_product_ids[1 + (abs(hashtext(s.customer_id || k::text)) % 10)],
         'v-' || (1 + abs(hashtext(s.customer_id)) % 10),
         s.is_control, 'shown', NULL, NULL, false,
         json_build_object('seed', true, 'bucketed', true),
         'grp-' || s.customer_id,
         s.seen_at, s.seen_at
    FROM seed_shopper s,
         LATERAL generate_series(1, 1 + abs(hashtext(s.customer_id)) % 3) k;

  GET DIAGNOSTICS v_impressions = ROW_COUNT;

  -- ---- accepted impressions --------------------------------------------
  -- Inserted rather than updated, so an influenced shopper has both the offers
  -- they ignored and the one they took — which is what makes the Overview
  -- accept rate a real ratio instead of a second random number.
  --
  -- The amounts are a split of that order's attributed total, so
  -- SUM(revenue_added) per placement and the purchase_attributions breakdown
  -- below are the same money counted once.
  INSERT INTO offer_impressions
    (id,shop_id,session_id,customer_id,surface,offer_type,offer_id,variant_id,
     is_control,outcome,outcome_at,revenue_added,paid,metadata,impression_group_id,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, v_shop_id,
         'seed-' || f.customer_id, f.customer_id,
         v_surfaces[1 + (abs(hashtext(f.order_id || k::text)) % 4)],
         'product',
         v_product_ids[1 + (abs(hashtext(f.order_id || k::text)) % 10)],
         'v-' || (1 + abs(hashtext(f.order_id)) % 10),
         false, 'accepted', f.order_date,
         CASE WHEN f.n_accepted = 1 THEN f.attributed
              WHEN k = 1            THEN round(f.attributed * 0.6, 2)
              ELSE f.attributed - round(f.attributed * 0.6, 2) END,
         true,
         json_build_object('seed', true, 'bucketed', true),
         'grp-' || f.customer_id,
         f.order_date - interval '20 minutes', f.order_date
    FROM seed_influenced f,
         LATERAL generate_series(1, f.n_accepted) k;

  -- ---- customers and orders --------------------------------------------
  INSERT INTO customer_data (id,customer_id,first_name,last_name,total_spent,order_count,last_order_date,verified_email,tax_exempt,is_active,shop_id,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, s.customer_id, 'Customer',
         '#' || substring(s.customer_id from 6),
         COALESCE(o.spent, 0)::float, COALESCE(o.n, 0), o.last_order,
         true, false, true, v_shop_id, s.seen_at - interval '10 days', now()
    FROM seed_shopper s
    LEFT JOIN (
      SELECT customer_id, SUM(total_amount) AS spent, COUNT(*) AS n, MAX(order_date) AS last_order
        FROM seed_order GROUP BY customer_id
    ) o ON o.customer_id = s.customer_id
  ON CONFLICT DO NOTHING;

  -- `customer_id` is what lift_service joins orders to impressions on, so it
  -- has to be the same string on both sides or every shopper reads as a
  -- non-converter and the whole Proof page collapses to zero lift.
  INSERT INTO order_data (id,order_id,order_name,customer_id,total_amount,subtotal_amount,total_tax_amount,order_date,processed_at,confirmed,test,cancelled_at,financial_status,fulfillment_status,currency_code,note_attributes,shop_id,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, o.order_id,
         '#' || (1400 + row_number() OVER (ORDER BY o.order_date))::text,
         o.customer_id, o.total_amount::float,
         round(o.total_amount * 0.92, 2)::float,
         round(o.total_amount * 0.08, 2)::float,
         o.order_date, o.order_date, true, false, NULL,
         'paid', 'fulfilled', 'USD', '[]'::json, v_shop_id, o.order_date, o.order_date
    FROM seed_order o
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS v_orders = ROW_COUNT;

  -- ---- attributions -----------------------------------------------------
  -- Keyed by PLACEMENT and summed, which is what the attribution engine writes
  -- and what the Overview table reads. No 'total' key: the engine has never
  -- written one, and the old seed's `total` was 40% of `total_revenue` on the
  -- same row, so the row contradicted itself.
  INSERT INTO purchase_attributions
    (id,shop_id,session_id,order_id,customer_id,contributing_extensions,attribution_weights,
     total_revenue,attributed_revenue,total_interactions,interactions_by_extension,
     purchase_at,attribution_algorithm,metadata,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, v_shop_id, NULL, f.order_id, f.customer_id,
         a.contributing, a.weights,
         a.total, a.by_surface, a.n, a.counts,
         f.order_date, 'direct_click', json_build_object('seed', true),
         f.order_date, f.order_date
    FROM seed_influenced f
    JOIN LATERAL (
      SELECT SUM(i.rev)                                            AS total,
             SUM(i.cnt)::int                                        AS n,
             json_object_agg(i.surface, i.rev)                      AS by_surface,
             json_object_agg(i.surface, i.cnt)                      AS counts,
             json_object_agg(i.surface, 1.0)                        AS weights,
             json_agg(json_build_object('extension_type', i.surface,
                                        'attributed_amount', i.rev,
                                        'attribution_weight', 1.0)) AS contributing
        FROM (
          SELECT surface, SUM(revenue_added) AS rev, COUNT(*)::int AS cnt
            FROM offer_impressions
           WHERE shop_id = v_shop_id AND paid AND customer_id = f.customer_id
           GROUP BY surface
        ) i
    ) a ON true;

  -- ---- commissions ------------------------------------------------------
  -- Two running totals, because the merchant crosses a phase boundary inside
  -- the window: attributed revenue accumulates until it passes the trial
  -- threshold, then commission accumulates until it hits the cycle cap.
  --
  -- `commission_earned` is what the rate implies; `commission_charged` is what
  -- the cap allows. The difference is overflow, and it is the whole reason the
  -- billing page can promise a ceiling.
  CREATE TEMP TABLE seed_commission ON COMMIT DROP AS
  WITH phased AS (
    SELECT f.order_id, f.order_date, f.attributed,
           round(f.attributed * c_rate, 2) AS earned,
           SUM(f.attributed) OVER w - f.attributed AS attr_before
      FROM seed_influenced f
    WINDOW w AS (ORDER BY f.order_date, f.order_id)
  ), tagged AS (
    SELECT p.*,
           CASE WHEN p.attr_before < c_trial_threshold THEN 'TRIAL' ELSE 'PAID' END AS phase
      FROM phased p
  )
  SELECT t.*,
         COALESCE(SUM(t.earned) FILTER (WHERE t.phase = 'PAID')
                  OVER (ORDER BY t.order_date, t.order_id), 0) AS paid_run_after
    FROM tagged t;

  SELECT MIN(order_date) INTO v_trial_end FROM seed_commission WHERE phase = 'PAID';
  v_trial_end := COALESCE(v_trial_end, now());

  -- One open cycle, starting when the trial ended. Its window has to contain
  -- every PAID commission, because getCurrentCycleUsage filters on order_date
  -- between start_date and end_date — a cycle that starts after them reports
  -- an empty cycle on a shop that has been billing all month.
  v_cycle_id := gen_random_uuid()::varchar;
  INSERT INTO billing_cycles (id,shop_subscription_id,cycle_number,start_date,end_date,period_fee,initial_cap_amount,current_cap_amount,usage_amount,commission_count,status,activated_at,cycle_metadata,created_at,updated_at)
  VALUES (v_cycle_id, v_sub_id, 1, v_trial_end, v_trial_end + interval '30 days',
          0.00, c_cap, c_cap, 0.00, 0, 'ACTIVE', v_trial_end, 'seed', v_trial_end, now());

  INSERT INTO commission_records
    (id,shop_id,purchase_attribution_id,billing_cycle_id,order_id,order_date,attributed_revenue,
     commission_rate,commission_earned,commission_charged,commission_overflow,
     billing_cycle_start,billing_cycle_end,cycle_usage_before,cycle_usage_after,
     capped_amount,trial_accumulated,billing_phase,status,charge_type,currency,error_count,created_at,updated_at)
  SELECT gen_random_uuid()::varchar, v_shop_id, pa.id,
         CASE WHEN c.phase = 'PAID' THEN v_cycle_id ELSE NULL END,
         c.order_id, c.order_date, c.attributed, c_rate, c.earned,
         CASE WHEN c.phase = 'PAID'
              THEN GREATEST(0, LEAST(c.paid_run_after, c_cap)
                             - LEAST(c.paid_run_after - c.earned, c_cap))
              ELSE 0.00 END,
         CASE WHEN c.phase = 'PAID'
              THEN c.earned - GREATEST(0, LEAST(c.paid_run_after, c_cap)
                                        - LEAST(c.paid_run_after - c.earned, c_cap))
              ELSE 0.00 END,
         CASE WHEN c.phase = 'PAID' THEN v_trial_end END,
         CASE WHEN c.phase = 'PAID' THEN v_trial_end + interval '30 days' END,
         CASE WHEN c.phase = 'PAID' THEN LEAST(c.paid_run_after - c.earned, c_cap) ELSE 0.00 END,
         CASE WHEN c.phase = 'PAID' THEN LEAST(c.paid_run_after, c_cap) ELSE 0.00 END,
         c_cap,
         CASE WHEN c.phase = 'TRIAL' THEN c.attr_before + c.attributed ELSE 0.00 END,
         c.phase::billing_phase_enum, 'RECORDED', 'FULL', 'USD', 0,
         c.order_date, c.order_date
    FROM seed_commission c
    JOIN purchase_attributions pa
      ON pa.shop_id = v_shop_id AND pa.order_id = c.order_id;

  -- The cycle's own totals are an aggregate of its rows, never a second guess.
  UPDATE billing_cycles b
     SET usage_amount     = agg.charged,
         commission_count = agg.n,
         updated_at       = now()
    FROM (
      SELECT COALESCE(SUM(commission_charged), 0) AS charged, COUNT(*) AS n
        FROM commission_records
       WHERE shop_id = v_shop_id AND billing_cycle_id = v_cycle_id AND deleted_at IS NULL
    ) agg
   WHERE b.id = v_cycle_id;

  -- ---- subscription -----------------------------------------------------
  -- The shop earned past the trial threshold inside this window, so leaving it
  -- on TRIAL would have the Billing page showing a progress bar for a trial the
  -- data says finished on day two.
  --
  -- `shopify_subscription_id` matters: BillingService falls back to the DB only
  -- when it is set. Without one the page renders "trial completed — needs
  -- billing setup" however much billing history exists.
  UPDATE shop_subscriptions
     SET subscription_type       = 'PAID',
         status                  = 'ACTIVE',
         shopify_subscription_id = COALESCE(shopify_subscription_id, 'gid://shopify/AppSubscription/seed'),
         shopify_status          = 'ACTIVE',
         updated_at              = now()
   WHERE id = v_sub_id;

  SELECT COUNT(*) INTO v_ctrl_conv FROM seed_order WHERE is_control;
  SELECT COALESCE(SUM(attributed), 0) INTO v_attributed FROM seed_influenced;

  RAISE NOTICE '--------------------------------------------------';
  RAISE NOTICE 'Shoppers        % (% control)', c_shoppers, c_shoppers * c_holdout / 100;
  RAISE NOTICE 'Impressions     % shown + % accepted',
    v_impressions, (SELECT COUNT(*) FROM offer_impressions WHERE shop_id = v_shop_id AND paid);
  RAISE NOTICE 'Orders          % (% control converters, need 100 for Proof)', v_orders, v_ctrl_conv;
  RAISE NOTICE 'Influenced      % orders, % attributed',
    (SELECT COUNT(*) FROM seed_influenced), v_attributed;
  RAISE NOTICE 'Billed          % of % cap',
    (SELECT usage_amount FROM billing_cycles WHERE id = v_cycle_id), c_cap;
  RAISE NOTICE '--------------------------------------------------';
  RAISE NOTICE 'Now open /app/overview, /app/impact and /app/billing';
END $$;
