import type { Meta, StoryObj } from "@storybook/react";
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell, Badge } from "@/lib/ui";

const meta: Meta = {
  title: "UI/TableRow",
  tags: ["autodocs"],
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

const sampleRows = [
  { id: "1", name: "Tech Reviews", status: "active", videos: 42 },
  { id: "2", name: "Gaming Daily", status: "paused", videos: 18 },
  { id: "3", name: "Cooking Tips", status: "archived", videos: 7 },
];

export const Default: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <tr>
          <TableHead>Channel</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Videos</TableHead>
        </tr>
      </TableHeader>
      <TableBody>
        {sampleRows.map((row) => (
          <TableRow key={row.id}>
            <TableCell className="font-medium">{row.name}</TableCell>
            <TableCell>
              <Badge variant={row.status === "active" ? "success" : row.status === "paused" ? "warning" : "neutral"}>
                {row.status}
              </Badge>
            </TableCell>
            <TableCell className="text-right">{row.videos}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  ),
};

export const WithSelected: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <tr>
          <TableHead>Channel</TableHead>
          <TableHead>Videos</TableHead>
        </tr>
      </TableHeader>
      <TableBody>
        <TableRow selected>
          <TableCell className="font-medium">Tech Reviews (selected)</TableCell>
          <TableCell>42</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>Gaming Daily</TableCell>
          <TableCell>18</TableCell>
        </TableRow>
        <TableRow disabled>
          <TableCell>Archived Channel</TableCell>
          <TableCell>0</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};

export const CompactRows: Story = {
  render: () => (
    <Table>
      <TableHeader>
        <tr>
          <TableHead>Name</TableHead>
          <TableHead>Value</TableHead>
        </tr>
      </TableHeader>
      <TableBody>
        {sampleRows.map((row) => (
          <TableRow key={row.id}>
            <TableCell compact>{row.name}</TableCell>
            <TableCell compact className="text-right">
              {row.videos}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  ),
};
