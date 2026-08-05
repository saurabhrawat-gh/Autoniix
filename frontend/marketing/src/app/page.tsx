import Navbar from '@/components/Navbar'
import Hero from '@/components/Hero'
import Marquee from '@/components/Marquee'
import Features from '@/components/Features'
import HowItWorks from '@/components/HowItWorks'
import ProductPreview from '@/components/ProductPreview'
import Stats from '@/components/Stats'
import Pricing from '@/components/Pricing'
import MarketingFeatures from '@/components/MarketingFeatures'
import FinalCTA from '@/components/FinalCTA'
import Footer from '@/components/Footer'

export default function Home() {
  return (
    <main>
      <Navbar />
      <Hero />
      <Marquee />
      <Features />
      <HowItWorks />
      <ProductPreview />
      <Stats />
      <Pricing />
      <MarketingFeatures />
      <FinalCTA />
      <Footer />
    </main>
  )
}
