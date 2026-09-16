import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "@/lib/ui";

const meta: Meta<typeof Badge> = {
  title: "UI/Badge",
  component: Badge,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["neutral", "accent", "secondary", "success", "warning", "error", "info", "outline", "short", "long"],
    },
    size: { control: "select", options: ["sm", "md", "lg"] },
    children: { control: "text" },
  },
  args: { children: "Badge", variant: "neutral", size: "md" },
};

export default meta;
type Story = StoryObj<typeof Badge>;

export const Neutral: Story = { args: { variant: "neutral", children: "Neutral" } };
export const Accent: Story = { args: { variant: "accent", children: "Active" } };
export const Success: Story = { args: { variant: "success", children: "Published" } };
export const Warning: Story = { args: { variant: "warning", children: "Pending" } };
export const Error: Story = { args: { variant: "error", children: "Failed" } };
export const Info: Story = { args: { variant: "info", children: "Scheduled" } };
export const Short: Story = { args: { variant: "short", children: "Short" } };
export const Long: Story = { args: { variant: "long", children: "Long" } };

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2 p-4">
      {(
        ["neutral", "accent", "secondary", "success", "warning", "error", "info", "outline", "short", "long"] as const
      ).map((v) => (
        <Badge key={v} variant={v}>
          {v}
        </Badge>
      ))}
    </div>
  ),
};

export const AllSizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2 p-4">
      {(["sm", "md", "lg"] as const).map((s) => (
        <Badge key={s} variant="accent" size={s}>
          {s}
        </Badge>
      ))}
    </div>
  ),
};
