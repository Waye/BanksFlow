declare module 'react-plaid-link' {
  interface PlaidLinkOptions {
    token: string | null;
    onSuccess: (publicToken: string) => void;
    onExit?: () => void;
    onLoad?: () => void;
    onEvent?: (eventName: string, metadata: any) => void;
    language?: string;
    countryCodes?: string[];
    env?: 'sandbox' | 'development' | 'production';
  }

  interface PlaidLinkResult {
    open: () => void;
    ready: boolean;
  }

  export function usePlaidLink(options: PlaidLinkOptions): PlaidLinkResult;
} 