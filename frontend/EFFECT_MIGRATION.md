# Effect.ts Migration Guide for SCPA

## Overview

Effect.ts is a powerful functional programming library that provides:
- **Typed error handling** - No more `unknown` errors
- **Structured concurrency** - Automatic cancellation and cleanup
- **Composability** - Build complex operations from simple ones
- **Testability** - Effects are pure and easily mockable

## Files Created

1. **`src/lib/api-effect.ts`** - Effect-based API client
2. **`src/lib/use-effect.ts`** - React hooks for Effect
3. **`src/app/dashboard/page-effect.tsx`** - Example refactored page

## Quick Start

### 1. Basic Query with Effect

**Before (Imperative):**
```tsx
const [jobs, setJobs] = useState<JobData[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  (async () => {
    try {
      setLoading(true);
      const data = await api.getJobs();
      setJobs(data.jobs);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(false);
    }
  })();
}, []);
```

**After (Effect):**
```tsx
import { useQuery } from '@/lib/use-effect';
import { getJobs } from '@/lib/api-effect';

const { data, loading, error, reload } = useQuery({
  effect: getJobs(),
}, {
  baseUrl: API_BASE,
  getToken: () => api.getToken(),
}, []);

// data.jobs is typed as JobData[]
// error is a string or null
```

### 2. Parallel Data Fetching

**Before:**
```tsx
const [recs, setRecs] = useState([]);
const [apps, setApps] = useState([]);

useEffect(() => {
  (async () => {
    const [recsRes, appsRes] = await Promise.allSettled([
      api.getRecommendations(),
      api.getApplications(),
    ]);
    
    if (recsRes.status === 'fulfilled') setRecs(recsRes.value.recommendations);
    if (appsRes.status === 'fulfilled') setApps(appsRes.value.applications);
  })();
}, []);
```

**After:**
```tsx
import { fetchDashboardData } from '@/lib/api-effect';

// Pre-built composite effect handles parallel fetching
const { data } = useQuery({
  effect: fetchDashboardData(),
}, runOptions, []);

// data contains: recommendations, applications, learningPath, skills, errors
```

### 3. Mutations (Form Submissions)

**Before:**
```tsx
const handleSubmit = async () => {
  setLoading(true);
  try {
    await api.updateProfile({ name, email });
    showSuccess();
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
};
```

**After:**
```tsx
import { useMutation } from '@/lib/use-effect';
import { updateProfile } from '@/lib/api-effect';

const { mutate, state } = useMutation({
  mutationFn: (data) => updateProfile(data),
  onSuccess: () => showSuccess(),
  onError: (err) => showError(getErrorMessage(err)),
}, runOptions);

// In your form:
<button onClick={() => mutate({ name, email })} disabled={state.loading}>
  {state.loading ? 'Saving...' : 'Save'}
</button>
```

### 4. Error Handling with Typed Errors

**Before:**
```tsx
try {
  await api.login(email, password);
} catch (e) {
  if (e instanceof ApiError && e.status === 401) {
    // handle unauthorized
  } else if (e.message.includes('Network')) {
    // handle network error
  }
}
```

**After:**
```tsx
import { login, ApiErrorType } from '@/lib/api-effect';

const result = await runEffect(login(email, password), runOptions);

Either.match(result, {
  onLeft: (error) => {
    switch (error._tag) {
      case 'Unauthorized':
        return 'Sesi berakhir. Silakan login.';
      case 'NetworkError':
        return 'Tidak dapat terhubung ke server.';
      case 'ServerError':
        return 'Server error. Coba lagi nanti.';
      default:
        return getErrorMessage(error);
    }
  },
  onRight: (data) => {
    // Handle success
  },
});
```

### 5. Composing Effects

Build complex operations from simple ones:

```tsx
import { Effect, pipe } from 'effect';

// Create a composed effect
const fetchAndEnrich = pipe(
  getRecommendations(),
  Effect.map(data => data.recommendations.slice(0, 5)),
  Effect.flatMap(recs => 
    Effect.all(recs.map(r => getJobDetails(r.job_id)))
  ),
  Effect.retry({ times: 3 }), // Auto-retry on failure
  Effect.timeout('5 seconds'), // Add timeout
);

const { data } = useQuery({ effect: fetchAndEnrich }, runOptions, []);
```

### 6. Conditional Fetching

```tsx
const { data } = useQuery({
  effect: getRecommendations(),
  enabled: !!user, // Only fetch when user exists
}, runOptions, [user?.id]);
```

## Error Types Reference

| Error Type | Description | When It Occurs |
|------------|-------------|----------------|
| `NetworkError` | Cannot connect to server | Gateway down, DNS, CORS |
| `HttpError` | HTTP error response | 4xx errors (except 401/404) |
| `Unauthorized` | 401 response | Token expired/invalid |
| `NotFound` | 404 response | Endpoint doesn't exist |
| `ServerError` | 5xx response | Server-side failure |
| `ParseError` | JSON parse failure | Invalid response format |

## API Effects Available

All API methods have Effect equivalents in `api-effect.ts`:

```tsx
// Auth
login(email, password)
register(name, email, password)
getMe()

// Jobs
getJobs(filters?)
getJob(id)

// Recommendations
getRecommendations()

// Learning Path
getLearningPath()

// Applications
getApplications()
submitApplications(jobIds)

// Profile
updateProfile(data)
saveOnboarding(step, data)

// Composite
fetchDashboardData() // Parallel fetch of all dashboard data
fetchProfileData()   // Parallel fetch of profile + applications
```

## React Hooks API

### `useQuery`
```tsx
useQuery<A>(options, runOptions, deps): AsyncStateWithReload<A>

// Options:
- effect: Effect.Effect<A, ApiErrorType, never>
- enabled?: boolean
- onSuccess?: (data: A) => void
- onError?: (error: ApiErrorType) => void
```

### `useMutation`
```tsx
useMutation<A, Args>(options, runOptions): UseMutationResult<A, Args>

// Options:
- mutationFn: (...args: Args) => Effect.Effect<A, ApiErrorType, never>
- onSuccess?: (data: A) => void
- onError?: (error: ApiErrorType) => void

// Returns:
- mutate: (...args: Args) => Promise<Either<A, string>>
- mutateAsync: (...args: Args) => Promise<A>
- state: { data, loading, error }
- reset: () => void
```

### `useAsyncEffect`
```tsx
useAsyncEffect<A>(
  createEffect: (signal: AbortSignal) => Effect.Effect<A, ApiErrorType, never>,
  deps: DependencyList,
  options: RunOptions,
  onError?: (error: ApiErrorType) => string
): AsyncStateWithReload<A>
```

## Migration Strategy

1. **Start small**: Pick one simple page (like `analytics/page.tsx`)
2. **Replace API calls**: Swap `api.getX()` with `getX()` from `api-effect.ts`
3. **Update error handling**: Use `getErrorMessage()` for user-friendly messages
4. **Add typed errors**: Gradually add specific error handling by `_tag`
5. **Compose**: Once comfortable, start combining multiple effects

## Benefits of Effect.ts

1. **Type Safety**: Errors are typed, not `unknown`
2. **Composability**: Build complex flows from simple effects
3. **Cancellation**: Automatic cleanup on component unmount
4. **Retry Logic**: Built-in retry with exponential backoff
5. **Testing**: Effects are pure and easily mockable
6. **Debugging**: Better stack traces and error context

## Next Steps

1. Review the example in `dashboard/page-effect.tsx`
2. Try migrating one simple page
3. Use the typed error handling for better UX
4. Explore Effect's advanced features (Schedule, Stream, Queue)

## Resources

- [Effect Documentation](https://effect.website/)
- [Effect GitHub](https://github.com/Effect-TS/effect)
- [Effect Discord](https://discord.gg/effect-ts)
