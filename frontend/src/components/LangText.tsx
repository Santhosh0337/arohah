import type { ReactNode } from "react";
import type { Language } from "../api/types.ts";
import { fontStack, langAttr } from "../lib/languages.ts";

/**
 * Wraps text in a language so the browser picks the right glyphs, and so the
 * font comes from font_family in languages.json (bible 16.5).
 */
export default function LangText({
  language,
  code,
  as: Tag = "span",
  className,
  children,
}: {
  language?: Language;
  code?: string | null;
  as?: "span" | "p" | "div";
  className?: string;
  children: ReactNode;
}) {
  const lang = langAttr(language?.code ?? code);
  return (
    <Tag lang={lang} className={className} style={language ? { fontFamily: fontStack(language) } : undefined}>
      {children}
    </Tag>
  );
}
