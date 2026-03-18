import { createClient } from '@/lib/supabase/server'
import { DashboardClient } from '@/components/dashboard/DashboardClient'

export const dynamic = 'force-dynamic'

export default async function DashboardPage() {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  const accessToken = session?.access_token ?? ''

  return (
    <div>
      <h2 className="text-xl font-bold mb-6">Your Watchlist</h2>
      <DashboardClient accessToken={accessToken} />
    </div>
  )
}
