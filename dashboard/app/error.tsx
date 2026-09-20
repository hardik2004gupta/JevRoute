"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#FAFAF9",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-inter, sans-serif)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 480, padding: "0 24px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 12,
            color: "#EF4444",
            letterSpacing: "0.08em",
            marginBottom: 16,
          }}
        >
          APPLICATION ERROR
        </div>
        <h1
          style={{
            fontSize: 18,
            fontWeight: 600,
            color: "#111827",
            marginBottom: 8,
          }}
        >
          Something went wrong
        </h1>
        <p style={{ fontSize: 14, color: "#6B7280", marginBottom: 24 }}>
          An unexpected error occurred. The dashboard could not render this page.
        </p>
        <button
          onClick={reset}
          style={{
            padding: "8px 20px",
            background: "#111827",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
