import type { Metadata } from "next";
import "./globals.css";
import { Atmosphere } from "@/components/Atmosphere";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { OfferBanner } from "@/components/OfferBanner";
import { Providers } from "@/components/Providers";
import { VerifyBanner } from "@/components/VerifyBanner";
import { SITE, sget } from "@/lib/server";
import { themeBootScript } from "@/lib/theme";

export const dynamic = "force-dynamic"; // content comes from the API (editable by the super admin), never frozen at build time

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: "ClubOS: run your club properly", template: "%s · ClubOS" },
  description: "Members, events, QR tickets and email for clubs and student organizations. Free for clubs of up to 100 people.",
  openGraph: { type: "website", siteName: "ClubOS" },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [content, offers] = await Promise.all([sget("/content"), sget("/offers/active")]);
  return (
    <html lang="en" suppressHydrationWarning>  {/* data-mode is owned by the boot script + ThemeProvider, never by React */}
      <head><script dangerouslySetInnerHTML={{ __html: themeBootScript }} /></head>
      <body>
        <Providers>
          <Atmosphere />
          <OfferBanner offers={offers || []} />
          <VerifyBanner />
          <Nav brand={content?.["site.brand"]} nav={content?.["nav"]} />
          <main>{children}</main>
          <Footer brand={content?.["site.brand"]} footer={content?.["footer"]} />
        </Providers>
      </body>
    </html>
  );
}
