import Link from "next/link";

export default function NotFound() {
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
            color: "#6B7280",
            letterSpacing: "0.08em",
            marginBottom: 16,
          }}
        >
          404 — NOT FOUND
        </div>
        <h1
          style={{
            fontSize: 18,
            fontWeight: 600,
            color: "#111827",
            marginBottom: 8,
          }}
        >
          Page not found
        </h1>
        <p style={{ fontSize: 14, color: "#6B7280", marginBottom: 24 }}>
          This page does not exist. Return to the benchmark dashboard.
        </p>
        <Link
          href="/"
          style={{
            padding: "8px 20px",
            background: "#111827",
            color: "#fff",
            borderRadius: 6,
            fontSize: 13,
            textDecoration: "none",
            display: "inline-block",
          }}
        >
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}
