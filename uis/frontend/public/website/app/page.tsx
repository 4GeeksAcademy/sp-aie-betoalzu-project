import { HeroSection } from "@/components/HeroSection";
import { ImpactSection } from "@/components/ImpactSection";
import { ServicesSection } from "@/components/ServicesSection";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function HomePage() {
  return (
    <>
      <SiteHeader currentPage="home" />
      <main>
        <HeroSection />
        <ServicesSection />
        <ImpactSection />
      </main>
      <SiteFooter />
    </>
  );
}
