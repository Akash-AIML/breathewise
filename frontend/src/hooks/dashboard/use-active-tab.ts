"use client";

import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { TabId } from "@/components/dashboard/navigation-tabs";

export interface ActiveTabState {
  activeTab: TabId;
  setActiveTab: Dispatch<SetStateAction<TabId>>;
}

/** Tab selection plus the cross-component "open assistant" event. */
export function useActiveTab(): ActiveTabState {
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  useEffect(() => {
    const onOpenAssistant = () => {
      setActiveTab("assistant");
    };
    window.addEventListener("breathewise:open-assistant", onOpenAssistant);
    return () => window.removeEventListener("breathewise:open-assistant", onOpenAssistant);
  }, []);

  return { activeTab, setActiveTab };
}
