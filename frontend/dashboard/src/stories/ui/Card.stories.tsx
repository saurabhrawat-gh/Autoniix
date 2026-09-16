import type { Meta, StoryObj } from "@storybook/react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, Button, Badge } from "@/lib/ui";

const meta: Meta<typeof Card> = {
  title: "UI/Card",
  component: Card,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "elevated", "flat", "in-progress", "interactive"],
    },
    padding: {
      control: "select",
      options: ["none", "sm", "md", "lg", "xl"],
    },
  },
  args: { variant: "default", padding: "none" },
};

export default meta;
type Story = StoryObj<typeof Card>;

export const Default: Story = {
  render: (args) => (
    <Card {...args} className="w-80">
      <CardHeader>
        <CardTitle>Channel: Tech Insights</CardTitle>
        <CardDescription>AI-powered YouTube content automation</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-content-secondary">3 videos published this week</p>
      </CardContent>
      <CardFooter>
        <Button size="sm" variant="secondary">
          Settings
        </Button>
        <Button size="sm">Trigger</Button>
      </CardFooter>
    </Card>
  ),
};

export const Elevated: Story = {
  args: { variant: "elevated", padding: "lg" },
  render: (args) => (
    <Card {...args} className="w-80">
      <p className="text-content-primary font-semibold mb-1">Elevated Card</p>
      <p className="text-sm text-content-secondary">Higher shadow elevation for modals or featured content.</p>
    </Card>
  ),
};

export const Interactive: Story = {
  args: { variant: "interactive", padding: "md" },
  render: (args) => (
    <Card {...args} className="w-80 cursor-pointer">
      <div className="flex items-center justify-between">
        <p className="text-content-primary font-medium">Click me</p>
        <Badge variant="success">Active</Badge>
      </div>
      <p className="text-sm text-content-secondary mt-1">Hover to see elevation effect.</p>
    </Card>
  ),
};

export const Flat: Story = {
  args: { variant: "flat", padding: "md" },
  render: (args) => (
    <Card {...args} className="w-80">
      <p className="text-content-primary">Flat card — no shadow, used inside surfaces.</p>
    </Card>
  ),
};
