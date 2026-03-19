'use client'

import { Button } from '@/components/ui/button'

interface BilingualToggleProps {
  lang: 'vi' | 'en'
  onLanguageChange: (lang: 'vi' | 'en') => void
}

export function BilingualToggle({ lang, onLanguageChange }: BilingualToggleProps) {
  return (
    <div
      className="fixed top-4 right-4 z-50 flex gap-1"
      aria-label="Report language"
      role="group"
    >
      <Button
        variant={lang === 'vi' ? 'default' : 'outline'}
        size="sm"
        className="px-4 py-2 text-sm"
        onClick={() => onLanguageChange('vi')}
        aria-pressed={lang === 'vi'}
      >
        VI
      </Button>
      <Button
        variant={lang === 'en' ? 'default' : 'outline'}
        size="sm"
        className="px-4 py-2 text-sm"
        onClick={() => onLanguageChange('en')}
        aria-pressed={lang === 'en'}
      >
        EN
      </Button>
    </div>
  )
}
