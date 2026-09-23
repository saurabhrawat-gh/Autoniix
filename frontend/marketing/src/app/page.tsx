import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import ModelStrip from "@/components/ModelStrip";
import Pipeline from "@/components/Pipeline";
import Features from "@/components/Features";
import CommandCenter from "@/components/CommandCenter";
import Stats from "@/components/Stats";
import Pricing from "@/components/Pricing";
import FAQ from "@/components/FAQ";
import FinalCTA from "@/components/FinalCTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main>
      <Navbar />
      <Hero />
      <ModelStrip />
      <Pipeline />
      <Features />
      <CommandCenter />
      <Stats />
      <Pricing />
      <FAQ />
      <FinalCTA />
      <Footer />
    </main>
  );
}
