import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = {
  title: "ERSELMETZ AI Command Center",
  description: "Private local AI command center",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
