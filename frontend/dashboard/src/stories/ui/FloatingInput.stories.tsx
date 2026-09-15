import type { Meta, StoryObj } from "@storybook/react";
import { FloatingInput } from "@/lib/ui";
import { Eye } from "lucide-react";

const meta: Meta<typeof FloatingInput> = {
  title: "UI/FloatingInput",
  component: FloatingInput,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj<typeof FloatingInput>;

export const Default: Story = {
  args: { label: "Email address", type: "email" },
};

export const WithValue: Story = {
  args: { label: "Channel name", defaultValue: "My Awesome Channel" },
};

export const WithHint: Story = {
  args: {
    label: "Handle",
    hint: "This will be shown as @handle on your profile.",
  },
};

export const ErrorState: Story = {
  args: {
    label: "Handle",
    error: true,
    hint: "Handle is already taken.",
    defaultValue: "my_channel",
  },
};

export const Password: Story = {
  args: {
    label: "Password",
    type: "password",
    rightSlot: <Eye size={16} className="text-content-tertiary cursor-pointer" />,
  },
};

export const Disabled: Story = {
  args: {
    label: "Workspace ID",
    defaultValue: "ws_abc123",
    disabled: true,
  },
};
