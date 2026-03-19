'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ReportMarkdownProps {
  content: string
  lang: 'vi' | 'en'
}

export function ReportMarkdown({ content, lang }: ReportMarkdownProps) {
  return (
    <article lang={lang} className="prose prose-zinc dark:prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </article>
  )
}
