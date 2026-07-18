from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        # Remove PricingTier FK from ShopSubscription
        migrations.RemoveField(
            model_name="shopsubscription",
            name="pricing_tier",
        ),
        # Remove legacy usage-based field
        migrations.RemoveField(
            model_name="shopsubscription",
            name="user_chosen_cap_amount",
        ),
        # Remove legacy commission rate from SubscriptionPlan
        migrations.RemoveField(
            model_name="subscriptionplan",
            name="default_commission_rate",
        ),
        # Add flat fee fields to SubscriptionPlan
        migrations.AddField(
            model_name="subscriptionplan",
            name="monthly_fee",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Flat monthly fee for the plan",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="trial_days",
            field=models.IntegerField(
                blank=True, help_text="Number of days for free trial", null=True
            ),
        ),
        # Delete PricingTier model
        migrations.DeleteModel(
            name="PricingTier",
        ),
    ]
