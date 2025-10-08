// features/onboarding/hooks/useOnboarding.ts
import { useNavigation } from "@remix-run/react";

export function useOnboarding() {
  const navigation = useNavigation();

  return {
    isLoading: navigation.state === "submitting",
    isSubmitting: navigation.state === "submitting",
  };
}
