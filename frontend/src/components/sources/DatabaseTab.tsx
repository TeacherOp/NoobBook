/**
 * DatabaseTab Component
 * Educational Note: Tab for adding database connections as sources.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Database, Spinner } from '@phosphor-icons/react';

interface DatabaseTabProps {
  onAddDatabase: (name: string, connectionString: string) => Promise<void>;
  isAtLimit: boolean;
}

export const DatabaseTab: React.FC<DatabaseTabProps> = ({
  onAddDatabase,
  isAtLimit,
}) => {
  const [name, setName] = useState('');
  const [dbType, setDbType] = useState<'postgresql' | 'mysql'>('postgresql');
  const [host, setHost] = useState('');
  const [port, setPort] = useState('');
  const [database, setDatabase] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const isPasswordWeak = password.length > 0 && password.length < 8;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !host.trim() || !database.trim() || !username.trim() || !password.trim()) return;

    setLoading(true);
    try {
      const defaultPort = dbType === 'postgresql' ? '5432' : '3306';
      const actualPort = port || defaultPort;
      const connectionString = `${dbType}://${username}:${password}@${host}:${actualPort}/${database}`;
      
      await onAddDatabase(name.trim(), connectionString);
      
      // Reset form
      setName('');
      setHost('');
      setPort('');
      setDatabase('');
      setUsername('');
      setPassword('');
    } catch (error) {
      console.error('Error adding database:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Database className="h-4 w-4" />
        <span>Connect to PostgreSQL or MySQL databases</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Security Warning */}
        {window.location.protocol !== 'https:' && (
          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">
              ⚠️ Warning: Connection not secure. Database credentials will be transmitted over HTTP.
            </p>
          </div>
        )}

        <div>
          <Label htmlFor="db-name">Display Name</Label>
          <Input
            id="db-name"
            type="text"
            placeholder="My Database"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading || isAtLimit}
          />
        </div>

        <div>
          <Label htmlFor="db-type">Database Type</Label>
          <Select value={dbType} onValueChange={(value: 'postgresql' | 'mysql') => setDbType(value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="postgresql">PostgreSQL</SelectItem>
              <SelectItem value="mysql">MySQL</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="db-host">Host</Label>
            <Input
              id="db-host"
              type="text"
              placeholder="localhost"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              disabled={loading || isAtLimit}
            />
          </div>
          <div>
            <Label htmlFor="db-port">Port</Label>
            <Input
              id="db-port"
              type="text"
              placeholder={dbType === 'postgresql' ? '5432' : '3306'}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              disabled={loading || isAtLimit}
            />
          </div>
        </div>

        <div>
          <Label htmlFor="db-database">Database Name</Label>
          <Input
            id="db-database"
            type="text"
            placeholder="mydb"
            value={database}
            onChange={(e) => setDatabase(e.target.value)}
            disabled={loading || isAtLimit}
          />
        </div>

        <div>
          <Label htmlFor="db-username">Username</Label>
          <Input
            id="db-username"
            type="text"
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={loading || isAtLimit}
          />
        </div>

        <div>
          <Label htmlFor="db-password">Password</Label>
          <Input
            id="db-password"
            type="password"
            placeholder="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading || isAtLimit}
          />
          {isPasswordWeak && (
            <p className="text-xs text-yellow-600 mt-1">
              Warning: Password should be at least 8 characters for security
            </p>
          )}
        </div>

        <Button
          type="submit"
          disabled={
            loading ||
            isAtLimit ||
            !name.trim() ||
            !host.trim() ||
            !database.trim() ||
            !username.trim() ||
            !password.trim()
          }
          className="w-full"
        >
          {loading ? (
            <>
              <Spinner className="mr-2 h-4 w-4 animate-spin" />
              Connecting...
            </>
          ) : (
            'Add Database'
          )}
        </Button>
      </form>

      {isAtLimit && (
        <p className="text-sm text-muted-foreground">
          You've reached the maximum number of sources for this project.
        </p>
      )}
    </div>
  );
};
