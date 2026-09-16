import type { Meta, StoryObj } from "@storybook/react";
import { Avatar } from "@/lib/ui";

const meta: Meta<typeof Avatar> = {
  title: "UI/Avatar",
  component: Avatar,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof Avatar>;

export const Initials: Story = {
  args: { fallback: "John Doe" },
};

export const SizeSm: Story = {
  args: { size: "sm", fallback: "Jane Smith" },
};

export const SizeMd: Story = {
  args: { size: "md", fallback: "Alice B" },
};

export const SizeLg: Story = {
  args: { size: "lg", fallback: "Bob C" },
};

export const WithImage: Story = {
  args: {
    size: "lg",
    src: "https://i.pravatar.cc/150?img=3",
    alt: "Sample user",
    fallback: "Sample User",
  },
};

export const BrokenImage: Story = {
  args: {
    size: "lg",
    src: "https://broken.example.com/no-image.jpg",
    fallback: "Broken Image",
  },
};

export const AvatarRow: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <Avatar size="sm" fallback="Alice" />
      <Avatar size="md" fallback="Bob" />
      <Avatar size="lg" fallback="Carol" />
    </div>
  ),
};
