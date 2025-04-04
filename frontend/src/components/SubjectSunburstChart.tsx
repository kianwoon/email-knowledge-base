import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Box, Text, useColorModeValue } from '@chakra-ui/react';

// Define expected data structure (simplified)
interface ChartNode {
  name: string;
  value?: number; // Optional for outer ring
  children?: ChartNode[];
}

interface SunburstChartProps {
  data: {
    name: string; // Root name (e.g., "Subjects")
    children: ChartNode[]; // Array of tags
  };
}

// Define distinct colors for segments
// Using a predefined categorical color scheme
const COLORS_OUTER = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#0088fe', '#00c49f', '#ffbb28', '#ff8042'];
// Function to generate shades for inner ring based on outer color
const getInnerColors = (outerColor: string, count: number): string[] => {
  // Basic shade generation (example - needs refinement for better visuals)
  const colors: string[] = [];
  const baseSaturation = 70;
  const baseLightness = 60;
  for (let i = 0; i < count; i++) {
    // Modify lightness slightly for each inner segment
    const lightness = baseLightness + (i * 10) % 30; // Simple variation
    colors.push(`hsl(${getHue(outerColor)}, ${baseSaturation}%, ${lightness}%)`);
  }
  return colors;
};

// Helper to get HSL hue from a hex color (basic approximation)
const getHue = (hex: string): number => {
  // This is a very simplified conversion and might not be accurate
  // Consider using a proper color library (like tinycolor2) if needed
  if (hex === '#8884d8') return 243;
  if (hex === '#82ca9d') return 145;
  if (hex === '#ffc658') return 45;
  if (hex === '#ff7300') return 27;
  if (hex === '#0088fe') return 210;
  if (hex === '#00c49f') return 165;
  if (hex === '#ffbb28') return 45;
  if (hex === '#ff8042') return 20;
  return Math.random() * 360; // Fallback
};


const SubjectSunburstChart: React.FC<SunburstChartProps> = ({ data }) => {
  const tooltipBg = useColorModeValue('white', 'gray.700');
  const tooltipColor = useColorModeValue('gray.800', 'white');

  if (!data || !data.children || data.children.length === 0) {
    return <Text>No analysis data available to display chart.</Text>;
  }

  // Prepare data for outer ring (tags)
  const outerData = data.children.map(tagNode => ({
    name: tagNode.name,
    // Sum values of children clusters for the outer ring size
    value: tagNode.children?.reduce((sum, cluster) => sum + (cluster.value || 0), 0) || 0,
    children: tagNode.children // Keep children for inner ring calculation
  }));

  // Prepare data for inner ring (clusters), associating colors
  const innerData: any[] = [];
  outerData.forEach((tagNode, index) => {
    if (tagNode.children) {
      const outerColor = COLORS_OUTER[index % COLORS_OUTER.length];
      const innerRingColors = getInnerColors(outerColor, tagNode.children.length);
      tagNode.children.forEach((clusterNode, innerIndex) => {
        innerData.push({
          ...clusterNode,
          // Add tag name for tooltip clarity
          tagName: tagNode.name, 
          // Assign a fill color based on the outer ring segment
          fill: innerRingColors[innerIndex % innerRingColors.length]
        });
      });
    }
  });

  return (
    <Box width="100%" height={400}> 
      <ResponsiveContainer>
        <PieChart>
          <Tooltip 
             contentStyle={{ backgroundColor: tooltipBg, color: tooltipColor, borderRadius: '5px' }} 
             formatter={(value: number, name: string, props: any) => [
               `${value} email${value !== 1 ? 's' : ''}`, // Value (count)
               `${props.payload.payload.tagName ? props.payload.payload.tagName + ' / ' : ''}${name}` // Name (Tag / Cluster or just Tag)
             ]}
           />
          {/* Outer Ring (Tags) */}
          <Pie
            data={outerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius="60%" 
            innerRadius="40%" // Create donut hole
            fill="#8884d8" // Base fill, overridden by Cell
            paddingAngle={1}
          >
            {outerData.map((entry, index) => (
              <Cell key={`cell-outer-${index}`} fill={COLORS_OUTER[index % COLORS_OUTER.length]} />
            ))}
          </Pie>
          {/* Inner Ring (Clusters) */}
          <Pie
            data={innerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius="40%" // Starts where outer ring inner radius ends
            innerRadius="20%" // Smaller inner hole
            fill="#82ca9d" // Base fill, overridden by data
            paddingAngle={1}
          >
            {/* Cells use fill property assigned during innerData creation */}
             {innerData.map((entry, index) => (
              <Cell key={`cell-inner-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </Box>
  );
};

export default SubjectSunburstChart; 