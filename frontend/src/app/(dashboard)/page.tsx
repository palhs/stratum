import { createClient } from '@/lib/supabase/server'

export const dynamic = 'force-dynamic'

export default async function DashboardPage() {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  const accessToken = session?.access_token ?? ''

  return (
    <div>
      <h2 className="text-xl font-bold mb-6">Your Watchlist</h2>
      {/* DashboardClient will be added in Plan 02 */}
      <p className="text-muted-foreground">Dashboard loading...</p>
    </div>
  )
}
