#!/bin/bash
# Switches the hosted tutor from Stripe test mode to live mode. Asks for the two live secrets
# without echoing them (they never reach a chat or the shell history), sets them and the live
# price on Vercel, and redeploys. Afterwards, enable the webhook destination "luckyj-tutor-billing"
# in the Stripe Dashboard (live mode, Workbench > Webhooks), which was created disabled.
#
# The key needs: Checkout Sessions (write), Subscriptions (read), Customer portal (write), and the
# portal configurations (write). A standard live secret key (sk_live_...) has all of them.
set -euo pipefail
cd "$(dirname "$0")/../.."   # the repository root, where `vercel link` was run

LIVE_PRICE=price_1UcDIgJ2EnCOYis01IRn9hvo   # LuckyJ AI Mahjong Tutor, $20/month, live mode

read -rsp "Live secret key (sk_live_... or rk_live_...): " KEY; echo
read -rsp "Live webhook signing secret (whsec_...): " WH; echo
case "$KEY" in sk_live_*|rk_live_*) ;; *) echo "That is not a live key; nothing changed."; exit 1;; esac
case "$WH" in whsec_*) ;; *) echo "That is not a webhook signing secret; nothing changed."; exit 1;; esac

for name in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_PRICE_ID STRIPE_PORTAL_CONFIG; do
  vercel env rm "$name" production --yes >/dev/null 2>&1 || true
done
printf %s "$KEY" | vercel env add STRIPE_SECRET_KEY production --sensitive >/dev/null
printf %s "$WH" | vercel env add STRIPE_WEBHOOK_SECRET production --sensitive >/dev/null
printf %s "$LIVE_PRICE" | vercel env add STRIPE_PRICE_ID production >/dev/null
unset KEY WH
echo "Live keys and price set on Vercel. Deploying..."
vercel deploy --prod --yes >/dev/null
echo "Done. Now enable luckyj-tutor-billing in Stripe (live mode, Workbench > Webhooks)."
