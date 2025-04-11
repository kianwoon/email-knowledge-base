// Existing interfaces (SharePointSite, SharePointDrive, SharePointItem)
export interface SharePointSite {
    id: string;
    name?: string;
    displayName: string;
    webUrl: string;
}

export interface SharePointDrive {
    id: string;
    name?: string;
    driveType?: string;
    webUrl: string;
}

export interface SharePointItem {
    id: string;
    name?: string;
    webUrl: string;
    size?: number;
    createdDateTime?: string;
    lastModifiedDateTime?: string;
    isFolder: boolean;
    isFile: boolean;
}

// --- New Interfaces for Insights ---

export interface ResourceReference {
    webUrl?: string;
    id?: string;
    type?: string;
}

export interface ResourceVisualization {
    title?: string;
    type?: string; // e.g., Word, Excel etc.
    previewImageUrl?: string;
}

export interface UsedInsight {
    id: string;
    resourceVisualization?: ResourceVisualization;
    resourceReference?: ResourceReference;
    // Add lastUsed fields if needed later
}

// Placeholder for SharedInsight
export interface SharedInsight {
    id: string;
    resourceVisualization?: ResourceVisualization;
    resourceReference?: ResourceReference;
} 