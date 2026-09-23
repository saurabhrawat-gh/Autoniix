import BrandMark from "./ui/BrandMark";

const LINKS = {
  Product: [
    ["Product", "#product"],
    ["Pipeline", "#pipeline"],
    ["Features", "#features"],
    ["Pricing", "#pricing"],
  ],
  Company: [
    ["Dashboard", "https://dash.autoniix.com/login"],
    ["Status", "#"],
    ["Contact", "mailto:hello@autoniix.com"],
    ["Sales", "mailto:sales@autoniix.com"],
  ],
  Legal: [
    ["Privacy", "#"],
    ["Terms", "#"],
    ["Cookies", "#"],
  ],
};

const SOCIAL = [
  ["X", "https://twitter.com/autoniix", "X (Twitter)"],
  ["GH", "https://github.com/autoniix", "GitHub"],
  ["YT", "https://youtube.com/@autoniix", "YouTube"],
];

export default function Footer() {
  return (
    <footer className="border-t border-border bg-surface-bg/70">
      <div className="container-x pt-16 pb-8">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 mb-14">
          <div className="col-span-2">
            <a href="/" className="inline-flex items-center gap-2.5 mb-4">
              <BrandMark size={24} />
              <span className="text-[15px] font-semibold tracking-tight text-content-primary">Autoniix</span>
            </a>
            <p className="text-sm text-content-tertiary max-w-xs leading-relaxed">
              AI video generation and automation for YouTube. Research, script, voice, render, publish — on autopilot.
            </p>
            <div className="flex items-center gap-2 mt-6">
              {SOCIAL.map(([k, href, label]) => (
                <a
                  key={k}
                  href={href}
                  aria-label={label}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary w-9 h-9 p-0 rounded-lg font-mono text-[11px]"
                >
                  {k}
                </a>
              ))}
            </div>
          </div>

          {Object.entries(LINKS).map(([group, links]) => (
            <div key={group}>
              <p className="eyebrow mb-4">{group}</p>
              <ul className="space-y-2.5">
                {links.map(([label, href]) => (
                  <li key={label}>
                    <a
                      href={href}
                      className="text-sm text-content-secondary hover:text-content-primary transition-colors"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="hairline" />
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-6 text-xs text-content-tertiary">
          <p>© {new Date().getFullYear()} Autoniix. All rights reserved.</p>
          <p className="font-mono flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-status-success" /> All systems operational
          </p>
        </div>
      </div>
    </footer>
  );
}
