"use client";

import { createClient, type Session, type User } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

let client: ReturnType<typeof createClient> | null = null;

export function supabaseClient() {
  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
    throw new Error("Supabase Auth is not configured.");
  }
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
  }
  return client;
}

export async function signInWithGoogle(returnTo = "/") {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  sessionStorage.setItem("curriculum-auth-return-to", returnTo);
  const { error } = await supabaseClient().auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${origin}/auth/callback`,
    },
  });
  if (error) {
    throw error;
  }
}

export async function signOut() {
  await supabaseClient().auth.signOut();
}

export async function getSession(): Promise<Session | null> {
  const { data, error } = await supabaseClient().auth.getSession();
  if (error) {
    throw error;
  }
  return data.session;
}

export async function completeOAuthCallback(callbackUrl: string): Promise<Session | null> {
  const url = new URL(callbackUrl);
  if (url.searchParams.has("code")) {
    const { data, error } = await supabaseClient().auth.exchangeCodeForSession(callbackUrl);
    if (error) {
      throw error;
    }
    return data.session;
  }
  return getSession();
}

export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  if (!session) {
    return null;
  }

  const expiresAtMs = session.expires_at ? session.expires_at * 1000 : 0;
  const shouldRefresh = expiresAtMs > 0 && expiresAtMs - Date.now() < 60_000;
  if (!shouldRefresh) {
    return session.access_token || null;
  }

  const { data, error } = await supabaseClient().auth.refreshSession();
  if (error) {
    throw error;
  }
  return data.session?.access_token || session.access_token || null;
}

export async function getCurrentUser(): Promise<User | null> {
  const { data, error } = await supabaseClient().auth.getUser();
  if (error) {
    return null;
  }
  return data.user;
}

export function redirectToLogin(returnTo?: string) {
  if (typeof window === "undefined") return;
  const target = returnTo || `${window.location.pathname}${window.location.search}`;
  sessionStorage.setItem("curriculum-auth-return-to", target);
  window.location.href = `/login?returnTo=${encodeURIComponent(target)}`;
}
