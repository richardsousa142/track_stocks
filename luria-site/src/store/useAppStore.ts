import { create } from 'zustand';
import type { AssetType } from '../types';
import { DEFAULT_MINI_INDICATORS } from '../config/indicators';

interface AppState {
  activeTab: AssetType;
  setActiveTab: (tab: AssetType) => void;

  selectedMiniIndicators: string[];
  toggleMiniIndicator: (code: string) => void;
  setMiniIndicators: (codes: string[]) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'acoes',
  setActiveTab: (tab) => set({ activeTab: tab }),

  selectedMiniIndicators: [...DEFAULT_MINI_INDICATORS],
  toggleMiniIndicator: (code) =>
    set((state) => ({
      selectedMiniIndicators: state.selectedMiniIndicators.includes(code)
        ? state.selectedMiniIndicators.filter((c) => c !== code)
        : [...state.selectedMiniIndicators, code],
    })),
  setMiniIndicators: (codes) => set({ selectedMiniIndicators: codes }),
}));
