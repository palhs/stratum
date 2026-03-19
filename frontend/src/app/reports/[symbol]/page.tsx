import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { ReportPageClient } from '@/components/report/ReportPageClient'

export const dynamic = 'force-dynamic'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ symbol: string }>
}) {
  const { symbol } = await params
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) redirect('/login')
  return <ReportPageClient symbol={symbol.toUpperCase()} accessToken={session.access_token} />
}
