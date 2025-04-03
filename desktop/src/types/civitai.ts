export interface CivitaiModel {
  id: number;
  name: string;
  type: string;
  description: string;
  nsfw: boolean;
  tags: string[];
  stats: {
    downloadCount: number;
    ratingCount: number;
    rating: number;
    commentCount: number;
    thumbsUpCount: number;
  };
  modelVersions: Array<{
    id: number;
    name: string;
    description: string;
    createdAt: string;
    downloadUrl: string;
    trainedWords: string[];
    files: Array<{
      name: string;
      id: number;
      sizeKB: number;
      type: string;
      metadata: {
        fp?: 'fp16' | 'fp32';
        size?: 'full' | 'pruned';
        format?: 'SafeTensor' | 'PickleTensor';
      };
      downloadUrl: string;
    }>;
    images: Array<{
      url: string;
      nsfw: boolean;
      width: number;
      height: number;
      hash: string;
      meta: any;
    }>;
  }>;
  metadata: {
    totalItems: number;
    currentPage: number;
    pageSize: number;
    totalPages: number;
    nextPage?: string;
  };
} 