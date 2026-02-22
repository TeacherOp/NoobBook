/**
 * IntegrationsSection Component
 * Manages Google Drive and Database connections.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Eye,
  EyeSlash,
  Trash,
  CircleNotch,
  GoogleDriveLogo,
  SignOut,
  ArrowSquareOut,
  Warning,
} from '@phosphor-icons/react';
import { googleDriveAPI, databasesAPI } from '@/lib/api/settings';
import type { GoogleStatus, DatabaseConnection, DatabaseType } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('integrations-section');

interface IntegrationsSectionProps {
  isAdmin?: boolean;
}

export const IntegrationsSection: React.FC<IntegrationsSectionProps> = ({ isAdmin = false }) => {
  // Google Drive State
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus>({
    configured: false,
    connected: false,
    email: null,
  });
  const [googleLoading, setGoogleLoading] = useState(false);

  // Database State
  const [dbConnections, setDbConnections] = useState<DatabaseConnection[]>([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbCreating, setDbCreating] = useState(false);
  const [dbValidating, setDbValidating] = useState(false);
  const [showDbUri, setShowDbUri] = useState(false);
  const [dbValidation, setDbValidation] = useState<{ valid?: boolean; message?: string }>({});
  const [dbForm, setDbForm] = useState<{
    name: string;
    db_type: DatabaseType;
    connection_uri: string;
    description: string;
  }>({
    name: '',
    db_type: 'postgresql',
    connection_uri: '',
    description: '',
  });

  // Confirmation dialog state
  const [deleteDbId, setDeleteDbId] = useState<string | null>(null);
  const [disconnectGoogleOpen, setDisconnectGoogleOpen] = useState(false);

  const { success, error, info } = useToast();

  useEffect(() => {
    loadGoogleStatus();
    loadDatabases();
  }, []);

  const loadGoogleStatus = async () => {
    try {
      const status = await googleDriveAPI.getStatus();
      setGoogleStatus(status);
    } catch (err) {
      log.error({ err }, 'failed to load Google status');
    }
  };

  const handleGoogleConnect = async () => {
    setGoogleLoading(true);
    try {
      const authUrl = await googleDriveAPI.getAuthUrl();
      if (authUrl) {
        window.open(authUrl, '_blank', 'width=500,height=600');
        info('Complete authentication in the new window');
        const pollInterval = setInterval(async () => {
          const status = await googleDriveAPI.getStatus();
          if (status.connected) {
            clearInterval(pollInterval);
            setGoogleStatus(status);
            setGoogleLoading(false);
            success(`Connected as ${status.email}`);
          }
        }, 2000);
        setTimeout(() => {
          clearInterval(pollInterval);
          setGoogleLoading(false);
        }, 120000);
      } else {
        error('Failed to get Google auth URL. Check your credentials.');
        setGoogleLoading(false);
      }
    } catch (err) {
      log.error({ err }, 'failed to Lconnecting GoogleE');
      error('Failed to connect Google Drive');
      setGoogleLoading(false);
    }
  };

  const handleGoogleDisconnect = async () => {
    setGoogleLoading(true);
    try {
      const disconnected = await googleDriveAPI.disconnect();
      if (disconnected) {
        setGoogleStatus({ configured: googleStatus.configured, connected: false, email: null });
        success('Google Drive disconnected');
      } else {
        error('Failed to disconnect Google Drive');
      }
    } catch (err) {
      log.error({ err }, 'failed to Ldisconnecting GoogleE');
      error('Failed to disconnect Google Drive');
    } finally {
      setGoogleLoading(false);
    }
  };

  const loadDatabases = async () => {
    setDbLoading(true);
    try {
      const dbs = await databasesAPI.listDatabases();
      setDbConnections(dbs);
    } catch (err) {
      log.error({ err }, 'failed to load databases');
    } finally {
      setDbLoading(false);
    }
  };

  const handleValidateDatabase = async () => {
    setDbValidating(true);
    try {
      const result = await databasesAPI.validateDatabase(dbForm.db_type, dbForm.connection_uri);
      setDbValidation(result);
      if (result.valid) {
        success(result.message || 'Connection successful');
      } else {
        error(result.message || 'Validation failed');
      }
    } finally {
      setDbValidating(false);
    }
  };

  const handleCreateDatabase = async () => {
    setDbCreating(true);
    try {
      await databasesAPI.createDatabase({
        name: dbForm.name.trim(),
        db_type: dbForm.db_type,
        connection_uri: dbForm.connection_uri.trim(),
        description: dbForm.description.trim() || undefined,
      });
      success('Database connection saved');
      setDbForm({ name: '', db_type: 'postgresql', connection_uri: '', description: '' });
      setDbValidation({});
      await loadDatabases();
    } catch (err) {
      log.error({ err }, 'failed to create database');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to save database connection');
    } finally {
      setDbCreating(false);
    }
  };

  const handleDeleteDatabase = async (connectionId: string) => {
    try {
      await databasesAPI.deleteDatabase(connectionId);
      success('Database connection deleted');
      await loadDatabases();
    } catch (err) {
      log.error({ err }, 'failed to delete database');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to delete database connection');
    }
  };

  const handleToggleVisibility = async (connectionId: string, visibleToAll: boolean) => {
    // Optimistic update
    setDbConnections((prev) =>
      prev.map((db) => (db.id === connectionId ? { ...db, visible_to_all: visibleToAll } : db))
    );
    try {
      await databasesAPI.updateVisibility(connectionId, visibleToAll);
      success(visibleToAll ? 'Visible to all users' : 'Admin only');
    } catch (err) {
      // Revert on failure
      setDbConnections((prev) =>
        prev.map((db) => (db.id === connectionId ? { ...db, visible_to_all: !visibleToAll } : db))
      );
      log.error({ err }, 'failed to update visibility');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update visibility');
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">Integrations</h2>
        <p className="text-sm text-muted-foreground">
          Connect external services and databases
        </p>
      </div>

      {/* Google Drive Section */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Google Drive</h3>
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 rounded-lg border bg-muted/30">
            <GoogleDriveLogo size={32} weight="duotone" className="text-primary" />
            <div className="flex-1">
              {googleStatus.connected ? (
                <>
                  <p className="text-sm font-medium">Connected</p>
                  <p className="text-xs text-muted-foreground">{googleStatus.email}</p>
                </>
              ) : googleStatus.configured ? (
                <>
                  <p className="text-sm font-medium">Not Connected</p>
                  <p className="text-xs text-muted-foreground">Click connect to authorize Google Drive access</p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium">Not Configured</p>
                  <p className="text-xs text-muted-foreground">Add Google Client ID and Secret in API Keys first</p>
                </>
              )}
            </div>
            {googleStatus.connected ? (
              <Button
                variant="soft"
                size="sm"
                onClick={() => setDisconnectGoogleOpen(true)}
                disabled={googleLoading}
              >
                {googleLoading ? (
                  <CircleNotch size={16} className="animate-spin" />
                ) : (
                  <>
                    <SignOut size={16} className="mr-1" />
                    Disconnect
                  </>
                )}
              </Button>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={handleGoogleConnect}
                disabled={googleLoading || !googleStatus.configured}
              >
                {googleLoading ? (
                  <CircleNotch size={16} className="animate-spin" />
                ) : (
                  <>
                    <ArrowSquareOut size={16} className="mr-1" />
                    Connect
                  </>
                )}
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Import files directly from Google Drive. Setup: Create OAuth 2.0 credentials at{' '}
            <a
              href="https://console.cloud.google.com/apis/credentials"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Google Cloud Console
            </a>
          </p>
        </div>
      </div>

      {/* Database Connections Section — admin only */}
      {isAdmin && <>
      <Separator />

      <div>
        <h3 className="text-sm font-semibold mb-3">Database Connections</h3>
        <div className="space-y-4">
          {dbLoading ? (
            <div className="flex items-center justify-center py-6">
              <CircleNotch size={20} className="animate-spin" />
            </div>
          ) : (
            <>
              {dbConnections.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No database connections yet. Add one below to attach it as a DATABASE source in a project.
                </p>
              ) : (
                <div className="space-y-2">
                  {dbConnections.map((db) => (
                    <div
                      key={db.id}
                      className="flex items-start justify-between gap-4 rounded-lg border p-3 bg-muted/20"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium truncate">{db.name}</p>
                          <span className="text-[11px] text-muted-foreground">
                            {db.db_type}
                          </span>
                        </div>
                        {db.description && (
                          <p className="text-xs text-muted-foreground">{db.description}</p>
                        )}
                        <p className="text-xs text-muted-foreground font-mono break-all">
                          {db.connection_uri_masked}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <Switch
                            checked={db.visible_to_all}
                            onCheckedChange={(checked) => handleToggleVisibility(db.id, checked)}
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {db.visible_to_all ? 'All users' : 'Admin only'}
                          </span>
                        </label>
                        <Button
                          variant="soft"
                          size="sm"
                          onClick={() => setDeleteDbId(db.id)}
                        >
                          <Trash size={16} className="mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Add connection</p>

                <div className="grid gap-2">
                  <Label>Name</Label>
                  <Input
                    value={dbForm.name}
                    onChange={(e) => setDbForm((s) => ({ ...s, name: e.target.value }))}
                    placeholder="Analytics DB"
                  />
                </div>

                <div className="grid gap-2">
                  <Label>Type</Label>
                  <Select
                    value={dbForm.db_type}
                    onValueChange={(v) => {
                      setDbForm((s) => ({ ...s, db_type: v as DatabaseType }));
                      setDbValidation({});
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select database type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="postgresql">PostgreSQL</SelectItem>
                      <SelectItem value="mysql">MySQL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label>Connection URI</Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDbUri((s) => !s)}
                      type="button"
                    >
                      {showDbUri ? <EyeSlash size={16} /> : <Eye size={16} />}
                    </Button>
                  </div>
                  <Input
                    type={showDbUri ? 'text' : 'password'}
                    value={dbForm.connection_uri}
                    onChange={(e) => {
                      setDbForm((s) => ({ ...s, connection_uri: e.target.value }));
                      setDbValidation({});
                    }}
                    placeholder="postgresql://user:pass@host:5432/db"
                  />
                  {dbValidation.message && (
                    <p className={`text-xs ${dbValidation.valid ? 'text-green-600' : 'text-red-600'}`}>
                      {dbValidation.message}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Credentials are stored server-side. The UI will only display a masked URI after saving.
                  </p>
                </div>

                <div className="grid gap-2">
                  <Label>Description (optional)</Label>
                  <Input
                    value={dbForm.description}
                    onChange={(e) => setDbForm((s) => ({ ...s, description: e.target.value }))}
                    placeholder="Read-only reporting database"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="soft"
                    onClick={handleValidateDatabase}
                    disabled={dbValidating || !dbForm.connection_uri.trim()}
                  >
                    {dbValidating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Test connection'
                    )}
                  </Button>
                  <Button
                    onClick={handleCreateDatabase}
                    disabled={
                      dbCreating ||
                      !dbForm.name.trim() ||
                      !dbForm.connection_uri.trim()
                    }
                  >
                    {dbCreating ? (
                      <>
                        <CircleNotch size={16} className="mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save'
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Delete Database Confirmation */}
      <AlertDialog open={!!deleteDbId} onOpenChange={(open) => !open && setDeleteDbId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Delete Database Connection
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{dbConnections.find(db => db.id === deleteDbId)?.name}</strong>? Projects using this connection will lose access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDeleteDbId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteDbId) {
                  handleDeleteDatabase(deleteDbId);
                  setDeleteDbId(null);
                }
              }}
            >
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </>}

      {/* Disconnect Google Drive Confirmation */}
      <AlertDialog open={disconnectGoogleOpen} onOpenChange={setDisconnectGoogleOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Disconnect Google Drive
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to disconnect <strong>{googleStatus.email}</strong>? You'll need to re-authenticate to import files again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDisconnectGoogleOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                handleGoogleDisconnect();
                setDisconnectGoogleOpen(false);
              }}
            >
              Disconnect
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
