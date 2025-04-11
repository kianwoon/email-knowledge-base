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

// --- Interfaces for Insights API (/insights/used) --- 

export interface InsightResourceReference {
    webUrl?: string;
    id?: string;
    type?: string;
}

export interface InsightResourceVisualization {
    title?: string;
    type?: string;
    previewImageUrl?: string;
}

export interface UsedInsight {
    id: string;
    resourceVisualization?: InsightResourceVisualization;
    resourceReference?: InsightResourceReference;
}

// +++ Interfaces for /me/drive/recent Endpoint +++

export interface Identity {
    displayName?: string;
    // id?: string;
}

export interface IdentitySet {
    user?: Identity;
    // application?: Identity;
    // device?: Identity;
}

export interface FileInfo {
    mimeType?: string;
}

export interface FolderInfo {
    childCount?: number;
}

// Renamed to avoid conflict with existing SharePointItem
export interface RecentDriveItem {
    id: string;
    name?: string;
    webUrl?: string;
    createdDateTime?: string; // Dates are strings from JSON
    lastModifiedDateTime?: string;
    size?: number;
    lastModifiedBy?: IdentitySet;
    file?: FileInfo;
    folder?: FolderInfo;
    // Helper properties can be added in component logic if needed
    // is_folder?: boolean;
    // last_modifier_name?: string;
}

// --- End Interfaces for /me/drive/recent ---

// Placeholder for SharedInsight
export interface SharedInsight {
    id: string;
    resourceVisualization?: InsightResourceVisualization;
    resourceReference?: InsightResourceReference;
} 