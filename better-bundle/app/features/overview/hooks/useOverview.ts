// features/overview/hooks/useOverview.ts
import { useState, useEffect } from "react";

export function useOverview() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return {
    mounted,
  };
}
