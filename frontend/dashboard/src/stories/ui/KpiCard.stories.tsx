import type { Meta, StoryObj } from "@storybook/react";
import { KpiCard } from "@/lib/ui";
import { Video, Users, Zap } from "lucide-react";

const meta: Meta<typeof KpiCard> = {
  title: "UI/KpiCard",
  component: KpiCard,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof KpiCard>;

export const PositiveDelta: Story = {
  args: {
    label: "Videos delivered",
    value: "142",
    delta: 12,
    deltaLabel: "+12%",
    icon: <Video size={16} />,
  },
};

export const NegativeDelta: Story = {
  args: {
    label: "Active channels",
    value: "8",
    delta: -2,
    deltaLabel: "-2",
    icon: <Users size={16} />,
  },
};

export const FlatDelta: Story = {
  args: {
    label: "Queue jobs",
    value: "24",
    delta: 0,
    deltaLabel: "0%",
    icon: <Zap size={16} />,
  },
};

export const NoDelta: Story = {
  args: {
    label: "Total runtime",
    value: "36h",
  },
};

export const KpiRow: Story = {
  render: () => (
    <div className="grid grid-cols-3 gap-4 w-full max-w-2xl">
      <KpiCard label="Videos delivered" value="142" delta={12} icon={<Video size={16} />} />
      <KpiCard label="Active channels" value="8" delta={-2} icon={<Users size={16} />} />
      <KpiCard label="Queue jobs" value="24" delta={0} icon={<Zap size={16} />} />
    </div>
  ),
};
