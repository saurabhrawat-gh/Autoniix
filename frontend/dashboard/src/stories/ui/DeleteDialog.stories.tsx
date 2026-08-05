import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { DeleteDialog, Button } from '@/lib/ui';

const meta: Meta<typeof DeleteDialog> = {
  title: 'UI/DeleteDialog',
  component: DeleteDialog,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof DeleteDialog>;

export const Default: Story = {
  render: () => {
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button variant="destructive" onClick={() => setOpen(true)}>Delete channel</Button>
        <DeleteDialog
          open={open}
          onOpenChange={setOpen}
          onConfirm={() => setOpen(false)}
        />
      </>
    );
  },
};

export const CustomLabels: Story = {
  render: () => {
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button variant="destructive" onClick={() => setOpen(true)}>Archive workspace</Button>
        <DeleteDialog
          open={open}
          onOpenChange={setOpen}
          title="Archive this workspace?"
          description="All channels and jobs will be paused. You can restore it later."
          destructiveLabel="Archive"
          onConfirm={() => setOpen(false)}
        />
      </>
    );
  },
};

export const LoadingState: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <DeleteDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete channel?"
        description="This will permanently delete all associated content."
        loading={true}
        onConfirm={() => {}}
      />
    );
  },
};
