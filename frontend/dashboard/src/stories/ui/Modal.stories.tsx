import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import {
  Modal,
  ModalTrigger,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalFooter,
  Button,
} from "@/lib/ui";

const meta: Meta = {
  title: "UI/Modal",
  tags: ["autodocs"],
  parameters: { layout: "centered" },
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button>Open modal</Button>
      </ModalTrigger>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>Create workspace</ModalTitle>
          <ModalDescription>Give your workspace a name to get started.</ModalDescription>
        </ModalHeader>
        <ModalFooter>
          <Button variant="ghost" size="sm">
            Cancel
          </Button>
          <Button size="sm">Create</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  ),
};

export const Small: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button variant="secondary">Small modal</Button>
      </ModalTrigger>
      <ModalContent size="sm">
        <ModalHeader>
          <ModalTitle>Confirm action</ModalTitle>
          <ModalDescription>Are you sure you want to proceed?</ModalDescription>
        </ModalHeader>
        <ModalFooter>
          <Button variant="ghost" size="sm">
            No
          </Button>
          <Button size="sm">Yes</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  ),
};

export const Large: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button variant="secondary">Large modal</Button>
      </ModalTrigger>
      <ModalContent size="lg">
        <ModalHeader>
          <ModalTitle>Configure provider chain</ModalTitle>
          <ModalDescription>Set up the AI provider sequence for this channel.</ModalDescription>
        </ModalHeader>
        <div className="py-4 text-sm text-content-tertiary">Provider chain configuration UI would go here.</div>
        <ModalFooter>
          <Button variant="ghost" size="sm">
            Cancel
          </Button>
          <Button size="sm">Save configuration</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  ),
};

export const Drawer: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button variant="secondary">Open drawer</Button>
      </ModalTrigger>
      <ModalContent size="drawer">
        <div className="p-6 flex flex-col gap-4 flex-1">
          <ModalHeader>
            <ModalTitle>Channel settings</ModalTitle>
            <ModalDescription>Configure your channel preferences.</ModalDescription>
          </ModalHeader>
          <p className="text-sm text-content-tertiary">Drawer content goes here.</p>
        </div>
        <div className="border-t border-border px-6 py-4">
          <ModalFooter>
            <Button variant="ghost" size="sm">
              Cancel
            </Button>
            <Button size="sm">Save</Button>
          </ModalFooter>
        </div>
      </ModalContent>
    </Modal>
  ),
};
