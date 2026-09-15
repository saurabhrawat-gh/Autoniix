"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/api-v2";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isLoggedIn() ? "/dashboard" : "/login");
  }, [router]);
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
    </div>
  );
}
