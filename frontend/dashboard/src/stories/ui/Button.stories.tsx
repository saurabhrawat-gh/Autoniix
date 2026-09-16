import type { Meta, StoryObj } from "@storybook/react";
import { Plus, Trash2, ArrowRight } from "lucide-react";
import { Button } from "@/lib/ui";

const meta: Meta<typeof Button> = {
  title: "UI/Button",
  component: Button,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "ghost", "tonal", "destructive", "link", "outline"],
    },
    size: {
      control: "select",
      options: ["sm", "md", "lg", "xl", "icon", "icon-sm"],
    },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
    children: { control: "text" },
  },
  args: {
    children: "Button",
    variant: "primary",
    size: "md",
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = { args: { variant: "primary", children: "Save changes" } };

export const Secondary: Story = { args: { variant: "secondary", children: "Cancel" } };

export const Ghost: Story = { args: { variant: "ghost", children: "Learn more" } };

export const Tonal: Story = { args: { variant: "tonal", children: "Configure" } };

export const Destructive: Story = { args: { variant: "destructive", children: "Delete channel" } };

export const Link: Story = { args: { variant: "link", children: "View details" } };

export const Outline: Story = { args: { variant: "outline", children: "Export" } };

export const Loading: Story = { args: { loading: true, children: "Saving…" } };

export const Disabled: Story = { args: { disabled: true, children: "Unavailable" } };

export const Small: Story = { args: { size: "sm", children: "Small" } };

export const Large: Story = { args: { size: "lg", children: "Large" } };

export const WithLeftIcon: Story = {
  args: { children: "New channel", leftIcon: <Plus size={15} /> },
};

export const WithRightIcon: Story = {
  args: { variant: "secondary", children: "Continue", rightIcon: <ArrowRight size={15} /> },
};

export const IconButton: Story = {
  args: { size: "icon", variant: "ghost", children: <Trash2 size={16} />, "aria-label": "Delete" },
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3 p-4">
      {(["primary", "secondary", "ghost", "tonal", "destructive", "outline"] as const).map((v) => (
        <Button key={v} variant={v}>
          {v.charAt(0).toUpperCase() + v.slice(1)}
        </Button>
      ))}
    </div>
  ),
};

export const AllSizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3 p-4">
      {(["sm", "md", "lg", "xl"] as const).map((s) => (
        <Button key={s} size={s}>
          Size {s}
        </Button>
      ))}
    </div>
  ),
};
