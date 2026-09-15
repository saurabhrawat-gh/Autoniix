import type { Meta, StoryObj } from "@storybook/react";
import { ToastProvider, useToast, Button } from "@/lib/ui";

const meta: Meta = {
  title: "UI/Toast",
  tags: ["autodocs"],
  parameters: { layout: "centered" },
  decorators: [
    (Story) => (
      <ToastProvider>
        <Story />
      </ToastProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj;

function ToastDemo({ variant, message }: { variant: "success" | "error" | "warning" | "info"; message: string }) {
  const { toast } = useToast();
  return (
    <Button variant="secondary" onClick={() => toast({ variant, message })}>
      Show {variant} toast
    </Button>
  );
}

export const Success: Story = {
  render: () => (
    <ToastProvider>
      <ToastDemo variant="success" message="Channel created successfully!" />
    </ToastProvider>
  ),
};

export const Error: Story = {
  render: () => (
    <ToastProvider>
      <ToastDemo variant="error" message="Failed to save changes. Please try again." />
    </ToastProvider>
  ),
};

export const Warning: Story = {
  render: () => (
    <ToastProvider>
      <ToastDemo variant="warning" message="Your session expires in 5 minutes." />
    </ToastProvider>
  ),
};

export const Info: Story = {
  render: () => (
    <ToastProvider>
      <ToastDemo variant="info" message="Video is being processed in the background." />
    </ToastProvider>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <ToastProvider>
      <div className="flex flex-col gap-2">
        <ToastDemo variant="success" message="Action completed." />
        <ToastDemo variant="error" message="Something went wrong." />
        <ToastDemo variant="warning" message="Check your configuration." />
        <ToastDemo variant="info" message="New update available." />
      </div>
    </ToastProvider>
  ),
};
