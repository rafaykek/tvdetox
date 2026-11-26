package dev.tvkit.home;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Base64;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * tvkit Home: a launcher whose whole UI is the redesign page (assets/home.html, built by
 * skills/redesign/scripts/build.py). The page is self-contained: network loads are blocked and
 * navigation away from it is refused. The page asks this activity to open apps and inputs
 * through the small "TVKitHome" bridge below.
 */
public class MainActivity extends Activity {
    /** Start-up timings and the page's console go to logcat under this tag: adb logcat -s tvkitHome */
    private static final String TAG = "tvkitHome";
    private WebView web;
    /** The installed-apps list for the page, built in the background while the WebView starts. */
    private volatile FutureTask<String> appList;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        appList = new FutureTask<>(new Callable<String>() {
            @Override
            public String call() { return buildAppList(); }
        });
        new Thread(appList, "tvkit-apps").start();
        long t = SystemClock.uptimeMillis();
        web = new WebView(this);
        Log.i(TAG, "WebView created in " + (SystemClock.uptimeMillis() - t) + " ms");
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);          // file:///android_asset/home.html
        s.setAllowContentAccess(false);
        s.setBlockNetworkLoads(true);        // the page never needs the network
        s.setMediaPlaybackRequiresUserGesture(true);
        web.setBackgroundColor(Color.BLACK);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return true; // stay on the home page
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                Log.i(TAG, "page: " + m.message() + " (line " + m.lineNumber() + ")");
                return true;
            }
        });
        web.addJavascriptInterface(new Bridge(), "TVKitHome");
        web.loadUrl("file:///android_asset/home.html#launcher");
        setContentView(web);
        web.requestFocus();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        backToFirstApp(); // Home pressed while already home
    }

    @Override
    public void onBackPressed() {
        backToFirstApp(); // a home screen has nowhere to go back to
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        web.requestFocus();
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    private void backToFirstApp() {
        if (web != null) web.evaluateJavascript("window.tvkitHome && window.tvkitHome()", null);
    }

    private boolean start(final Intent intent) {
        if (intent == null || getPackageManager().resolveActivity(intent, 0) == null) return false;
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    startActivity(intent);
                } catch (ActivityNotFoundException | SecurityException ignored) {
                    // the page shows its own "Can't open" message when launch() returns false
                }
            }
        });
        return true;
    }

    /** A TV app and its label, read once (loadLabel is a resource lookup, too slow to call inside a sort). */
    private static final class App {
        final ResolveInfo ri;
        final String label;

        App(ResolveInfo ri, String label) {
            this.ri = ri;
            this.label = label;
        }
    }

    /**
     * Every app with a TV launcher entry, sorted by name, as JSON: package, label and TV banner (PNG data URI).
     * Runs on a background thread while the WebView starts. Drawing and PNG-encoding 30+ banners takes
     * seconds on a TV chip, so each banner is cached in cacheDir/banners until its app is updated.
     */
    private String buildAppList() {
        long t = SystemClock.uptimeMillis();
        PackageManager pm = getPackageManager();
        Intent query = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LEANBACK_LAUNCHER);
        List<App> apps = new ArrayList<>();
        for (ResolveInfo ri : pm.queryIntentActivities(query, 0)) {
            if (ri.activityInfo.packageName.equals(getPackageName())) continue;
            try {
                apps.add(new App(ri, String.valueOf(ri.loadLabel(pm))));
            } catch (RuntimeException ignored) {
                // skip an app whose label can't be read
            }
        }
        Collections.sort(apps, new Comparator<App>() {
            @Override
            public int compare(App a, App b) { return a.label.compareToIgnoreCase(b.label); }
        });
        File dir = new File(getCacheDir(), "banners");
        dir.mkdirs();
        Set<String> keep = new HashSet<>();
        int fromCache = 0;
        JSONArray list = new JSONArray();
        for (App a : apps) {
            String pkg = a.ri.activityInfo.packageName;
            try {
                JSONObject app = new JSONObject();
                app.put("package", pkg);
                app.put("label", a.label);
                long updated = 0;
                try {
                    updated = pm.getPackageInfo(pkg, 0).lastUpdateTime;
                } catch (PackageManager.NameNotFoundException ignored) {
                    // just uninstalled; the cache key still works
                }
                File f = new File(dir, pkg + "-" + updated + "-" + Integer.toHexString(a.ri.activityInfo.name.hashCode()) + ".png");
                keep.add(f.getName());
                byte[] png = read(f);
                if (png != null) {
                    fromCache++;
                } else {
                    Drawable banner = a.ri.activityInfo.loadBanner(pm);
                    if (banner == null) banner = a.ri.activityInfo.applicationInfo.loadBanner(pm);
                    if (banner != null) {
                        png = png(banner, 320, 180);
                        write(f, png);
                    }
                }
                if (png != null) app.put("banner", "data:image/png;base64," + Base64.encodeToString(png, Base64.NO_WRAP));
                list.put(app);
            } catch (JSONException | RuntimeException ignored) {
                // skip an app whose banner can't be read
            }
        }
        File[] old = dir.listFiles();
        if (old != null) {
            for (File f : old) {
                if (f.getName().endsWith(".png") && !keep.contains(f.getName())) f.delete(); // app updated or removed
            }
        }
        Log.i(TAG, "apps: " + list.length() + " apps (" + fromCache + " banners from cache) in "
                + (SystemClock.uptimeMillis() - t) + " ms");
        return list.toString();
    }

    /** Draws an app's banner into PNG bytes the page can show as the tile's logo. */
    private static byte[] png(Drawable d, int w, int h) {
        Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bmp);
        d.setBounds(0, 0, w, h);
        d.draw(canvas);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        bmp.compress(Bitmap.CompressFormat.PNG, 100, out);
        bmp.recycle();
        return out.toByteArray();
    }

    private static byte[] read(File f) {
        long len = f.length();
        if (!f.isFile() || len <= 0 || len > 4 << 20) return null;
        byte[] b = new byte[(int) len];
        try (FileInputStream in = new FileInputStream(f)) {
            int n = 0;
            while (n < b.length) {
                int r = in.read(b, n, b.length - n);
                if (r < 0) return null;
                n += r;
            }
            return b;
        } catch (IOException e) {
            return null;
        }
    }

    /** Writes through a temp file, so a half-written banner is never read back. */
    private static void write(File f, byte[] b) {
        File tmp = new File(f.getPath() + "." + Thread.currentThread().getId() + ".tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) {
            out.write(b);
        } catch (IOException e) {
            tmp.delete();
            return;
        }
        if (!tmp.renameTo(f)) tmp.delete();
    }

    private static String norm(String s) {
        return s == null ? "" : s.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    /** Methods the page can call as window.TVKitHome.*. Only these exist; they only open things. */
    private class Bridge {
        @JavascriptInterface
        public boolean launch(String pkg) {
            PackageManager pm = getPackageManager();
            Intent i = pm.getLeanbackLaunchIntentForPackage(pkg);
            if (i == null) i = pm.getLaunchIntentForPackage(pkg);
            if (i == null) return false;
            i.addFlags(Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            return start(i);
        }

        /** Opens an HDMI or other TV input by its label ("HDMI 1"), falling back to the n-th HDMI port. */
        @JavascriptInterface
        public boolean openInput(String label) {
            TvInputManager tim = (TvInputManager) getSystemService(Context.TV_INPUT_SERVICE);
            if (tim == null) return false;
            String want = norm(label);
            String id = null;
            List<TvInputInfo> hdmi = new ArrayList<>();
            for (TvInputInfo info : tim.getTvInputList()) {
                CharSequence name = info.loadLabel(MainActivity.this);
                if (id == null && want.equals(norm(name == null ? null : name.toString()))) id = info.getId();
                if (info.getType() == TvInputInfo.TYPE_HDMI && info.getParentId() == null) hdmi.add(info);
            }
            if (id == null) {
                Matcher m = Pattern.compile("hdmi(\\d+)").matcher(want);
                if (m.find()) {
                    Collections.sort(hdmi, new Comparator<TvInputInfo>() {
                        @Override
                        public int compare(TvInputInfo a, TvInputInfo b) { return a.getId().compareTo(b.getId()); }
                    });
                    int n = Integer.parseInt(m.group(1)) - 1;
                    if (n >= 0 && n < hdmi.size()) id = hdmi.get(n).getId();
                }
            }
            if (id == null) return false;
            return start(new Intent(Intent.ACTION_VIEW, TvContract.buildChannelUriForPassthroughInput(id)));
        }

        /** Every app with a TV launcher entry, sorted by name: package, label and TV banner (PNG data URI). */
        @JavascriptInterface
        public String apps() {
            try {
                return appList.get(20, TimeUnit.SECONDS); // normally finished before the page asks
            } catch (InterruptedException | ExecutionException | TimeoutException e) {
                Log.w(TAG, "background app list failed; building it now", e);
                return buildAppList();
            }
        }

        @JavascriptInterface
        public boolean openSettings() {
            return start(new Intent(Settings.ACTION_SETTINGS));
        }

        @JavascriptInterface
        public boolean search() {
            if (start(new Intent("android.search.action.GLOBAL_SEARCH"))) return true;
            return start(new Intent(Intent.ACTION_ASSIST));
        }
    }
}
