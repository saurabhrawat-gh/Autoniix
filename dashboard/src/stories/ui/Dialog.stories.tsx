import type { Meta, StoryObj } from '@storybook/react';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, Button } from '@/lib/ui';

const meta: Meta = {
  title: 'UI/Dialog',
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="secondary">Open dialog</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete channel?</DialogTitle>
          <DialogDescription>
            This will permanently delete the channel and all associated content. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary">Cancel</Button>
          <Button variant="destructive">Delete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};

export const WithForm: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button>New channel</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create channel</DialogTitle>
          <DialogDescription>Add a new YouTube channel to automate content for.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 py-2">
          <div>
            <label className="block text-xs font-medium text-content-secondary mb-1.5">Channel name</label>
            <input
              className="w-full h-11 px-3.5 text-sm rounded-[8px] bg-surface-0 border border-border text-content-primary focus:outline-none focus:ring-2 focus:ring-accent/10"
              placeholder="Tech Insights"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary">Cancel</Button>
          <Button>Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};
