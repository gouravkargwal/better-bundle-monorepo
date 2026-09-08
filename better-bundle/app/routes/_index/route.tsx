import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";

import { login } from "../../shopify.server";

import styles from "./styles.module.css";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);

  if (url.searchParams.get("shop")) {
    throw redirect(`/app?${url.searchParams.toString()}`);
  }

  return { showForm: Boolean(login) };
};

const FEATURES = [
  {
    title: "AI recommendations everywhere",
    text: "Personalized product suggestions on your product pages, cart, checkout, thank-you page, and post-purchase — all from one engine.",
  },
  {
    title: "Pay only for results",
    text: "No monthly fee. You pay a small commission on revenue we actually generate, capped per month. Free until we've driven meaningful sales.",
  },
  {
    title: "Know your true lift",
    text: "Causal A/B measurement with a control group, so you see incremental revenue — not just attributed numbers.",
  },
] as const;

export default function App() {
  const { showForm } = useLoaderData<typeof loader>();

  return (
    <div className={styles.index}>
      <div className={styles.content}>
        <h1 className={styles.heading}>
          AI-powered recommendations that grow your Shopify revenue
        </h1>
        <p className={styles.text}>
          BetterBundle analyzes your products, orders, and customers to show
          smart recommendations across your store — and only charges you when
          they work.
        </p>

        <ul className={styles.list}>
          {FEATURES.map((feature) => (
            <li key={feature.title}>
              <h2>{feature.title}</h2>
              <p>{feature.text}</p>
            </li>
          ))}
        </ul>

        {showForm && (
          <Form className={styles.form} method="post" action="/auth/login">
            <label className={styles.label}>
              <span>Shop domain</span>
              <input className={styles.input} type="text" name="shop" />
              <span>e.g: my-shop-domain.myshopify.com</span>
            </label>
            <button className={styles.button} type="submit">
              Log in
            </button>
          </Form>
        )}
      </div>
    </div>
  );
}