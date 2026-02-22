import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { useToast } from '../ui/toast';
import { authAPI } from '@/lib/api/auth';
import { createLogger } from '@/lib/logger';

const log = createLogger('auth-page');

interface AuthPageProps {
  onAuthenticated: () => Promise<void> | void;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthenticated }) => {
  const [portal, setPortal] = useState<'admin' | 'user'>('user');
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { success, error } = useToast();

  const handleSubmit = async () => {
    if (!email || !password) {
      error('Email and password are required');
      return;
    }

    setSubmitting(true);
    try {
      const result =
        mode === 'signin'
          ? await authAPI.signIn(email, password)
          : await authAPI.signUp(email, password);

      if (!result.success) {
        error(result.error || 'Authentication failed');
        return;
      }

      success(mode === 'signin' ? 'Signed in' : 'Account created');
      await onAuthenticated();
    } catch (err) {
      log.error({ err }, 'authentication failed');
      error('Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle>{portal === 'admin' ? 'Admin Access' : 'User Access'}</CardTitle>
          <CardDescription>
            {portal === 'admin'
              ? 'Admin portal — use an email listed in NOOBBOOK_ADMIN_EMAILS.'
              : 'User portal — standard access to chat and studio.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-6 flex gap-2">
            <Button
              variant={portal === 'admin' ? 'default' : 'outline'}
              size="sm"
              className="flex-1"
              onClick={() => setPortal('admin')}
              disabled={submitting}
            >
              Admin
            </Button>
            <Button
              variant={portal === 'user' ? 'default' : 'outline'}
              size="sm"
              className="flex-1"
              onClick={() => setPortal('user')}
              disabled={submitting}
            >
              User
            </Button>
          </div>
          <Tabs value={mode} onValueChange={(v) => setMode(v as 'signin' | 'signup')}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="signin">
                {portal === 'admin' ? 'Admin sign in' : 'Sign in'}
              </TabsTrigger>
              <TabsTrigger value="signup">
                {portal === 'admin' ? 'Admin sign up' : 'Sign up'}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="signin" className="mt-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="signin-email">Email</Label>
                <Input
                  id="signin-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signin-password">Password</Label>
                <Input
                  id="signin-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <Button className="w-full" onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Signing in…' : portal === 'admin' ? 'Sign in as admin' : 'Sign in'}
              </Button>
            </TabsContent>

            <TabsContent value="signup" className="mt-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="signup-email">Email</Label>
                <Input
                  id="signup-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signup-password">Password</Label>
                <Input
                  id="signup-password"
                  type="password"
                  placeholder="Create a password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <Button className="w-full" onClick={handleSubmit} disabled={submitting}>
                {submitting
                  ? 'Creating account…'
                  : portal === 'admin'
                    ? 'Create admin account'
                    : 'Create account'}
              </Button>
              {portal === 'admin' ? (
                <p className="text-xs text-muted-foreground">
                  Admin role is granted only if the email is in NOOBBOOK_ADMIN_EMAILS.
                </p>
              ) : null}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};
