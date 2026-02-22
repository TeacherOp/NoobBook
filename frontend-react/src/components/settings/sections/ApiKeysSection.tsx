/**
 * ApiKeysSection Component
 * Manages API keys for AI Models, Storage, and Utility services.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Eye,
  EyeSlash,
  Trash,
  Warning,
  CheckCircle,
  XCircle,
  CircleNotch,
} from '@phosphor-icons/react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { settingsAPI } from '@/lib/api/settings';
import type { ApiKey } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('api-keys-section');

interface ValidationState {
  [key: string]: {
    validating: boolean;
    valid?: boolean;
    message?: string;
  };
}

export const ApiKeysSection: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [modifiedKeys, setModifiedKeys] = useState<{ [key: string]: string }>({});
  const [showApiKeys, setShowApiKeys] = useState<{ [key: string]: boolean }>({});
  const [loading, setLoading] = useState(false);
  const [validationState, setValidationState] = useState<ValidationState>({});
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const { success, error, info } = useToast();

  useEffect(() => {
    loadApiKeys();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadApiKeys = async () => {
    setLoading(true);
    try {
      const keys = await settingsAPI.getApiKeys();
      setApiKeys(keys);
      setModifiedKeys({});
    } catch (err) {
      log.error({ err }, 'failed to load API keys');
      error('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  };

  const updateApiKey = (id: string, value: string) => {
    setModifiedKeys(prev => ({ ...prev, [id]: value }));
    setApiKeys(prev => prev.map(key =>
      key.id === id ? { ...key, value } : key
    ));
  };

  const toggleShowApiKey = (id: string) => {
    setShowApiKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const deleteApiKey = async (id: string) => {
    try {
      await settingsAPI.deleteApiKey(id);
      setModifiedKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[id];
        return newKeys;
      });
      setApiKeys(prev => prev.map(key =>
        key.id === id ? { ...key, value: '', is_set: false } : key
      ));
      success('API key deleted successfully');
    } catch (err) {
      log.error({ err }, 'failed to delete API key');
      error('Failed to delete API key');
    }
  };

  const validateApiKey = async (id: string) => {
    const value = modifiedKeys[id] || apiKeys.find(k => k.id === id)?.value || '';
    const keyName = apiKeys.find(k => k.id === id)?.name || id;

    if (value.includes('***')) {
      info('Cannot validate a masked API key. Please enter a new key.');
      return;
    }

    setValidationState(prev => ({
      ...prev,
      [id]: { validating: true }
    }));

    try {
      const result = await settingsAPI.validateApiKey(id, value);

      if (result.valid) {
        try {
          await settingsAPI.updateApiKeys([{ id, value }]);
          setModifiedKeys(prev => {
            const newKeys = { ...prev };
            delete newKeys[id];
            return newKeys;
          });
          setValidationState(prev => ({
            ...prev,
            [id]: {
              validating: false,
              valid: true,
              message: result.message
            }
          }));
          success(`${keyName} validated and saved successfully!`);
          await loadApiKeys();
        } catch (saveErr) {
          const saveErrorMessage = saveErr instanceof Error ? saveErr.message : 'Failed to save';
          setValidationState(prev => ({
            ...prev,
            [id]: {
              validating: false,
              valid: false,
              message: `Validation succeeded but save failed: ${saveErrorMessage}`
            }
          }));
          error(`Failed to save ${keyName}: ${saveErrorMessage}`);
        }
      } else {
        setValidationState(prev => ({
          ...prev,
          [id]: {
            validating: false,
            valid: false,
            message: result.message
          }
        }));
        error(`${keyName} validation failed: ${result.message}`);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Validation failed';
      setValidationState(prev => ({
        ...prev,
        [id]: {
          validating: false,
          valid: false,
          message: errorMessage
        }
      }));
      error(`Failed to validate ${keyName}: ${errorMessage}`);
    }
  };

  const renderApiKeyField = (apiKey: ApiKey) => (
    <div key={apiKey.id} className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="flex items-center gap-2">
          {apiKey.name}
          {apiKey.required && (
            <span className="text-xs text-destructive">*Required</span>
          )}
        </Label>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => toggleShowApiKey(apiKey.id)}
          >
            {showApiKeys[apiKey.id] ? (
              <EyeSlash size={16} />
            ) : (
              <Eye size={16} />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setDeleteConfirmId(apiKey.id)}
            disabled={!apiKey.value && !apiKey.is_set}
          >
            <Trash size={16} />
          </Button>
        </div>
      </div>
      <div className="flex gap-2">
        <Input
          type={showApiKeys[apiKey.id] ? 'text' : 'password'}
          placeholder={`Enter ${apiKey.name} key...`}
          value={modifiedKeys[apiKey.id] !== undefined ? modifiedKeys[apiKey.id] : apiKey.value}
          onChange={(e) => updateApiKey(apiKey.id, e.target.value)}
          className="font-mono text-sm flex-1"
        />
        <Button
          variant="default"
          size="sm"
          onClick={() => validateApiKey(apiKey.id)}
          disabled={!modifiedKeys[apiKey.id] || modifiedKeys[apiKey.id].includes('***') || validationState[apiKey.id]?.validating}
          className="min-w-[120px]"
        >
          {validationState[apiKey.id]?.validating ? (
            <>
              <CircleNotch size={16} className="animate-spin mr-1" />
              Saving...
            </>
          ) : (
            'Validate & Save'
          )}
        </Button>
      </div>
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">{apiKey.description}</p>
        {validationState[apiKey.id]?.message && (
          <div className={`flex items-center gap-1 text-xs ${
            validationState[apiKey.id]?.valid ? 'text-green-600' : 'text-red-600'
          }`}>
            {validationState[apiKey.id]?.valid ? (
              <CheckCircle size={12} />
            ) : (
              <XCircle size={12} />
            )}
            <span>{validationState[apiKey.id]?.message}</span>
          </div>
        )}
        {apiKey.is_set && !modifiedKeys[apiKey.id] && (
          <div className="flex items-center gap-1 text-xs text-green-600">
            <CheckCircle size={12} />
            <span>Configured</span>
          </div>
        )}
      </div>
    </div>
  );

  const renderCategorySection = (title: string, category: 'ai' | 'storage' | 'utility') => {
    const categoryKeys = apiKeys.filter(k => k.category === category);
    if (categoryKeys.length === 0) return null;

    return (
      <div>
        <h3 className="text-sm font-semibold mb-3">{title}</h3>
        <div className="space-y-3">
          {categoryKeys.map(renderApiKeyField)}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <CircleNotch size={32} className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">API Keys</h2>
        <p className="text-sm text-muted-foreground">
          Configure API keys for AI models and services
        </p>
      </div>

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Warning size={16} />
        <p>API keys are securely stored in your backend .env file</p>
      </div>

      <div className="space-y-6">
        {renderCategorySection('AI Models', 'ai')}
        <Separator />
        {renderCategorySection('Storage & Database', 'storage')}
        <Separator />
        {renderCategorySection('Utility Services', 'utility')}
      </div>

      <AlertDialog open={!!deleteConfirmId} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Delete API Key
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{apiKeys.find(k => k.id === deleteConfirmId)?.name}</strong>? You'll need to re-enter it to use this service again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteConfirmId) {
                  deleteApiKey(deleteConfirmId);
                  setDeleteConfirmId(null);
                }
              }}
            >
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
