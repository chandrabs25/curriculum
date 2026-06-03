"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCurrentUser, signInWithGoogle } from "../services/auth";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [returnTo, setReturnTo] = useState("/");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const target = params.get("returnTo") || "/";
    setReturnTo(target);
    getCurrentUser()
      .then((user) => {
        if (user) {
          window.location.replace(target);
        }
      })
      .catch(() => {
        // Stay on login when the current session cannot be verified.
      });
  }, []);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError(null);
    try {
      await signInWithGoogle(returnTo);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start Google sign in.");
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-6 text-zinc-900">
      <main className="w-full max-w-sm rounded-xl border border-zinc-300 bg-white p-8">
        <Link href="/" className="text-xs font-medium text-zinc-500 hover:text-zinc-900">
          &larr; Home
        </Link>
        <h1 className="mt-6 text-2xl font-light tracking-tight text-zinc-950">Sign in</h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-500">
          Sign in to save curriculum plans, module designs, checkpoint results, and section-level learning insights.
        </p>
        {error && (
          <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            {error}
          </div>
        )}
        <button
          type="button"
          onClick={() => void handleGoogleSignIn()}
          disabled={loading}
          className="mt-8 flex w-full items-center justify-center rounded-full bg-zinc-900 px-5 py-3 text-xs font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Redirecting..." : "Continue with Google"}
        </button>
      </main>
    </div>
  );
}
