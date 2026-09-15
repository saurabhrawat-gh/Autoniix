import type { Meta, StoryObj } from "@storybook/react";
import { EmptyState, Button } from "@/lib/ui";
import { Video, Search, Inbox } from "lucide-react";

const meta: Meta<typeof EmptyState> = {
  title: "UI/EmptyState",
  component: EmptyState,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof EmptyState>;

export const Basic: Story = {
  args: {
    heading: "No channels yet",
    description: "Create your first channel to get started.",
  },
};

export const WithIcon: Story = {
  args: {
    icon: <Video size={32} />,
    heading: "No videos",
    description: "Your delivered videos will appear here.",
  },
};

export const WithAction: Story = {
  args: {
    icon: <Inbox size={32} />,
    heading: "No items to review",
    description: "All caught up! New review requests will appear here.",
    action: <Button>Check queue</Button>,
  },
};

export const SearchEmpty: Story = {
  args: {
    icon: <Search size={32} />,
    heading: "No results found",
    description: "Try a different search term or adjust your filters.",
    action: <Button variant="ghost">Clear filters</Button>,
  },
};
