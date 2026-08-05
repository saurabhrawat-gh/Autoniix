import type { Meta, StoryObj } from '@storybook/react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/lib/ui';

const meta: Meta = {
  title: 'UI/Tabs',
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Tabs defaultValue="overview" className="w-96">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="analytics">Analytics</TabsTrigger>
        <TabsTrigger value="settings">Settings</TabsTrigger>
      </TabsList>
      <TabsContent value="overview" className="p-4 text-sm text-content-secondary">
        Overview content here.
      </TabsContent>
      <TabsContent value="analytics" className="p-4 text-sm text-content-secondary">
        Analytics content here.
      </TabsContent>
      <TabsContent value="settings" className="p-4 text-sm text-content-secondary">
        Settings content here.
      </TabsContent>
    </Tabs>
  ),
};

export const WithDisabled: Story = {
  render: () => (
    <Tabs defaultValue="active" className="w-96">
      <TabsList>
        <TabsTrigger value="active">Active</TabsTrigger>
        <TabsTrigger value="paused">Paused</TabsTrigger>
        <TabsTrigger value="archived" disabled>Archived</TabsTrigger>
      </TabsList>
      <TabsContent value="active" className="p-4 text-sm text-content-secondary">Active channels</TabsContent>
      <TabsContent value="paused" className="p-4 text-sm text-content-secondary">Paused channels</TabsContent>
    </Tabs>
  ),
};
