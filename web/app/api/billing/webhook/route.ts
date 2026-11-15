// Stripe calls this for subscription events. The signature check needs the raw body.
import { NextResponse } from "next/server";
import { handleEvent, stripe } from "@/lib/billing";

export async function POST(request: Request) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  const signature = request.headers.get("stripe-signature");
  if (!secret || !signature) return NextResponse.json({ error: "not configured" }, { status: 400 });
  let event;
  try {
    event = stripe().webhooks.constructEvent(await request.text(), signature, secret);
  } catch {
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }
  try {
    const note = await handleEvent(event);
    console.log(`stripe ${event.type} ${event.id}: ${note}`);
    return NextResponse.json({ received: true });
  } catch (error) {
    console.error(`stripe ${event.type} ${event.id} failed`, error);
    return NextResponse.json({ error: "handler failed" }, { status: 500 }); // Stripe retries
  }
}
