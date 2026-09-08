export interface Category { id: number; name: string; description: string | null }
export interface Technician {
  id: number; first_name: string; last_name: string; phone: string; email: string | null
  category_id: number; category_name: string; escalation_order: number; is_team_leader: boolean
}
