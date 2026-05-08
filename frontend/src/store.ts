import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  name: string
  username?: string
  avatar?: string
  employee_id?: string
  department?: string
  position?: string
  phone?: string
  email?: string
  role?: string  // admin/user/viewer
  role_id?: number
  role_name?: string
  permissions?: {
    allowed_modules?: string[]
    allowed_routes?: string[]
  } | string[]
}

interface Project {
  id: number
  name: string
  leader: string
  status: string
  progress: number
}

interface DailyEntry {
  start_time: string
  end_time: string
  location?: string
  content: string
  project_hint?: string
  hours: number
  matched_project_id?: number
  matched_project_name?: string
  matched_task_id?: string
  matched_task_name?: string
  match_confidence?: number
  shared_period?: string  // 共享时间段
  period_total_hours?: number  // 该时间段的总工时
}

interface DailyDraft {
  inputText: string
  entries: DailyEntry[]
  selectedDate: string
  warnings: { type: string; message: string }[]
  matchedProjects: Array<{id: number; name: string; leader: string}>
  hasParsed: boolean
  updatedAt: string
}

interface AppState {
  // 用户状态
  user: User | null
  token: string | null
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  logout: () => void
  
  // 项目状态
  currentProject: Project | null
  setCurrentProject: (project: Project | null) => void
  
  // 日报状态（临时，不持久化）
  dailyEntries: DailyEntry[]
  setDailyEntries: (entries: DailyEntry[]) => void
  addDailyEntry: (entry: DailyEntry) => void
  removeDailyEntry: (index: number) => void
  clearDailyEntries: () => void
  
  // 日报草稿（持久化）
  dailyDraft: DailyDraft | null
  saveDailyDraft: (draft: DailyDraft) => void
  loadDailyDraft: () => DailyDraft | null
  clearDailyDraft: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      currentProject: null,
      dailyEntries: [],
      dailyDraft: null,
      
      setUser: (user: User | null) => set({ user }),
      setToken: (token: string | null) => set({ token }),
      logout: () => set({ user: null, token: null, currentProject: null, dailyEntries: [], dailyDraft: null }),
      
      setCurrentProject: (project: Project | null) => set({ currentProject: project }),
      
      setDailyEntries: (entries: DailyEntry[]) => set({ dailyEntries: entries }),
      addDailyEntry: (entry: DailyEntry) => set((state: AppState) => ({ 
        dailyEntries: [...state.dailyEntries, entry] 
      })),
      removeDailyEntry: (index: number) => set((state: AppState) => ({
        dailyEntries: state.dailyEntries.filter((_: DailyEntry, i: number) => i !== index)
      })),
      clearDailyEntries: () => set({ dailyEntries: [] }),
      
      // 草稿操作
      saveDailyDraft: (draft: DailyDraft) => set({ dailyDraft: draft }),
      loadDailyDraft: () => get().dailyDraft,
      clearDailyDraft: () => set({ dailyDraft: null }),
    }),
    {
      name: 'project-agent-storage',
      partialize: (state: AppState) => ({ 
        user: state.user, 
        token: state.token,
        currentProject: state.currentProject,
        dailyDraft: state.dailyDraft  // 持久化草稿
      }),
    }
  )
)
