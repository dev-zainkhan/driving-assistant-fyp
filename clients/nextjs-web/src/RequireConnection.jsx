"use client";
// Used by app/setup/layout.jsx and app/settings/layout.jsx: these pages need a connection,
// so opening one of them directly (without pressing Start) goes back to the Start screen.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDA } from "./DAProvider";

export function RequireConnection({ children, showErrors = false }) {
  const { da } = useDA();
  const router = useRouter();
  useEffect(() => {
    if (!da) router.replace("/");
  }, [da, router]);

  if (!da) return null;
  return (
    <>
      {children}
      {showErrors && da.error && (
        <div className="lp-toast" role="alert" onClick={da.clearError}>
          Not saved: {da.error}
        </div>
      )}
    </>
  );
}
