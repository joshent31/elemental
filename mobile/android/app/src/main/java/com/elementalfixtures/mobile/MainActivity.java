package com.elementalfixtures.mobile;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebStorage;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.zxing.ResultPoint;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int CAMERA_PERMISSION_REQUEST = 1001;
    private static final String PREFERENCES_NAME = "elemental_mobile";
    private static final String SITE_URL_KEY = "site_url";
    private static final String START_PATH = "/mobile-app";

    private WebView webView;
    private ProgressBar progressBar;
    private DecoratedBarcodeView nativeScanner;
    private Button closeScannerButton;
    private Button changeSiteButton;
    private LinearLayout setupPanel;
    private EditText siteUrlInput;
    private TextView setupError;
    private TextView siteLabel;
    private PermissionRequest pendingWebCameraRequest;
    private boolean nativeScannerPermissionPending;
    private String lastNativeScan;
    private long lastNativeScanAt;
    private Uri trustedOrigin;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createInterface();
        configureWebView();

        String configuredSite = getPreferences().getString(SITE_URL_KEY, "");
        if (configuredSite == null || configuredSite.isEmpty()) {
            showSiteSetup(false);
            return;
        }

        try {
            setTrustedSite(configuredSite);
            showBrowser();
            if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
                loadMobileApp();
            }
        } catch (IllegalArgumentException error) {
            getPreferences().edit().remove(SITE_URL_KEY).apply();
            showSiteSetup(false);
        }
    }

    private void createInterface() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(14), dp(4), dp(8), dp(4));
        toolbar.setBackgroundColor(Color.rgb(26, 41, 66));

        siteLabel = new TextView(this);
        siteLabel.setText(R.string.app_name);
        siteLabel.setTextColor(Color.WHITE);
        siteLabel.setTextSize(15);
        siteLabel.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.addView(siteLabel, new LinearLayout.LayoutParams(0, dp(48), 1));

        changeSiteButton = new Button(this);
        changeSiteButton.setText(R.string.change_site);
        changeSiteButton.setTextSize(11);
        changeSiteButton.setVisibility(View.GONE);
        changeSiteButton.setOnClickListener(view -> showSiteSetup(true));
        toolbar.addView(changeSiteButton, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                dp(40)
        ));
        root.addView(toolbar, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(52)
        ));

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1
        ));

        webView = new WebView(this);
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        content.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
        content.addView(progressBar, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                dp(4)
        ));

        configureNativeScanner(content);
        configureSiteSetup(content);
        setContentView(root);
    }

    private void configureSiteSetup(FrameLayout content) {
        setupPanel = new LinearLayout(this);
        setupPanel.setOrientation(LinearLayout.VERTICAL);
        setupPanel.setGravity(Gravity.CENTER_HORIZONTAL);
        setupPanel.setPadding(dp(28), dp(48), dp(28), dp(24));
        setupPanel.setBackgroundColor(Color.WHITE);

        TextView title = new TextView(this);
        title.setText(R.string.connect_site_title);
        title.setTextColor(Color.rgb(26, 41, 66));
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER);
        setupPanel.addView(title, matchWidthWrapHeight());

        TextView help = new TextView(this);
        help.setText(R.string.connect_site_help);
        help.setTextColor(Color.DKGRAY);
        help.setTextSize(14);
        help.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams helpLayout = matchWidthWrapHeight();
        helpLayout.topMargin = dp(12);
        setupPanel.addView(help, helpLayout);

        siteUrlInput = new EditText(this);
        siteUrlInput.setHint(R.string.site_url_hint);
        siteUrlInput.setSingleLine(true);
        siteUrlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        LinearLayout.LayoutParams inputLayout = matchWidthWrapHeight();
        inputLayout.topMargin = dp(28);
        setupPanel.addView(siteUrlInput, inputLayout);

        setupError = new TextView(this);
        setupError.setTextColor(Color.rgb(183, 28, 28));
        setupError.setTextSize(12);
        setupError.setVisibility(View.GONE);
        LinearLayout.LayoutParams errorLayout = matchWidthWrapHeight();
        errorLayout.topMargin = dp(8);
        setupPanel.addView(setupError, errorLayout);

        Button connectButton = new Button(this);
        connectButton.setText(R.string.connect_sign_in);
        connectButton.setOnClickListener(view -> connectToEnteredSite());
        LinearLayout.LayoutParams connectLayout = matchWidthWrapHeight();
        connectLayout.topMargin = dp(18);
        setupPanel.addView(connectButton, connectLayout);

        TextView securityNote = new TextView(this);
        securityNote.setText(R.string.http_security_note);
        securityNote.setTextColor(Color.GRAY);
        securityNote.setTextSize(11);
        securityNote.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams noteLayout = matchWidthWrapHeight();
        noteLayout.topMargin = dp(18);
        setupPanel.addView(securityNote, noteLayout);

        content.addView(setupPanel, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
    }

    private LinearLayout.LayoutParams matchWidthWrapHeight() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private void connectToEnteredSite() {
        try {
            String normalisedSite = normaliseSiteUrl(siteUrlInput.getText().toString());
            String previousSite = getPreferences().getString(SITE_URL_KEY, "");
            boolean changedSite = previousSite != null
                    && !previousSite.isEmpty()
                    && !previousSite.equals(normalisedSite);
            if (changedSite) {
                clearBrowserSession();
            }
            getPreferences().edit().putString(SITE_URL_KEY, normalisedSite).apply();
            setTrustedSite(normalisedSite);
            setupError.setVisibility(View.GONE);
            showBrowser();
            webView.clearHistory();
            loadMobileApp();
            if (normalisedSite.startsWith("http://")) {
                Toast.makeText(
                        this,
                        "Warning: this HTTP connection does not encrypt your login or ERP data.",
                        Toast.LENGTH_LONG
                ).show();
            }
        } catch (IllegalArgumentException error) {
            setupError.setText(error.getMessage());
            setupError.setVisibility(View.VISIBLE);
        }
    }

    private void showSiteSetup(boolean keepCurrentSite) {
        hideNativeScanner();
        setupPanel.setVisibility(View.VISIBLE);
        webView.setVisibility(View.GONE);
        progressBar.setVisibility(View.GONE);
        changeSiteButton.setVisibility(View.GONE);
        setupError.setVisibility(View.GONE);
        String currentSite = getPreferences().getString(SITE_URL_KEY, "");
        siteUrlInput.setText(keepCurrentSite && currentSite != null ? currentSite : "");
        siteUrlInput.requestFocus();
    }

    private void showBrowser() {
        setupPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        changeSiteButton.setVisibility(View.VISIBLE);
    }

    private void setTrustedSite(String siteUrl) {
        String normalisedSite = normaliseSiteUrl(siteUrl);
        trustedOrigin = Uri.parse(normalisedSite);
        String label = trustedOrigin.getHost();
        if (trustedOrigin.getPort() != -1) {
            label += ":" + trustedOrigin.getPort();
        }
        siteLabel.setText(label);
    }

    private void loadMobileApp() {
        if (trustedOrigin != null) {
            webView.loadUrl(joinUrl(trustedOrigin.toString(), START_PATH));
        }
    }

    private SharedPreferences getPreferences() {
        return getSharedPreferences(PREFERENCES_NAME, MODE_PRIVATE);
    }

    private void clearBrowserSession() {
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.removeAllCookies(null);
        cookieManager.flush();
        WebStorage.getInstance().deleteAllData();
        webView.clearCache(true);
        webView.clearHistory();
    }

    static String normaliseSiteUrl(String input) {
        String value = input == null ? "" : input.trim();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Enter a site address.");
        }
        if (!value.contains("://")) {
            value = "https://" + value;
        }
        Uri parsed = Uri.parse(value);
        String scheme = parsed.getScheme();
        if (!"https".equalsIgnoreCase(scheme) && !"http".equalsIgnoreCase(scheme)) {
            throw new IllegalArgumentException("The site must use an http:// or https:// address.");
        }
        if (parsed.getHost() == null || parsed.getHost().trim().isEmpty()) {
            throw new IllegalArgumentException("Enter a valid site address, for example https://erp.customer.com.");
        }
        if (parsed.getUserInfo() != null) {
            throw new IllegalArgumentException("Do not include a username or password in the site address.");
        }
        Uri.Builder origin = new Uri.Builder()
                .scheme(scheme.toLowerCase(Locale.ROOT))
                .encodedAuthority(parsed.getEncodedAuthority());
        return origin.build().toString();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setUserAgentString(settings.getUserAgentString() + " ElementalMobile/1.1");

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, false);
        webView.addJavascriptInterface(new ScannerBridge(), "ElementalAndroid");

        boolean debuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        WebView.setWebContentsDebuggingEnabled(debuggable);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                CookieManager.getInstance().flush();
                updateGateScreenMode(Uri.parse(url));
                installNativeScannerBridge();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    Toast.makeText(
                            MainActivity.this,
                            "Unable to reach this site. Check the address and network, or tap Change Site.",
                            Toast.LENGTH_LONG
                    ).show();
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return openExternallyIfNeeded(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return openExternallyIfNeeded(Uri.parse(url));
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> handleWebPermissionRequest(request));
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                if (request == pendingWebCameraRequest) {
                    pendingWebCameraRequest = null;
                }
            }
        });
    }

    private void configureNativeScanner(FrameLayout root) {
        nativeScanner = new DecoratedBarcodeView(this);
        nativeScanner.setStatusText("Point the camera at a QR code");
        nativeScanner.setVisibility(View.GONE);
        root.addView(nativeScanner, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));

        closeScannerButton = new Button(this);
        closeScannerButton.setText(R.string.close_camera);
        closeScannerButton.setTextColor(Color.BLACK);
        closeScannerButton.setBackgroundColor(Color.WHITE);
        closeScannerButton.setVisibility(View.GONE);
        closeScannerButton.setOnClickListener(view -> {
            hideNativeScanner();
            webView.evaluateJavascript(
                    "var b=document.getElementById('start-scan-gate');if(b){b.style.display='block';}",
                    null
            );
        });
        FrameLayout.LayoutParams closeLayout = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
        );
        closeLayout.bottomMargin = dp(40);
        root.addView(closeScannerButton, closeLayout);

        nativeScanner.decodeContinuous(new BarcodeCallback() {
            @Override
            public void barcodeResult(BarcodeResult result) {
                deliverNativeScan(result == null ? null : result.getText());
            }

            @Override
            public void possibleResultPoints(List<ResultPoint> resultPoints) {
                // The viewfinder renders these points itself.
            }
        });
    }

    private void installNativeScannerBridge() {
        if (!isCurrentPageTrusted()) {
            return;
        }
        String script = "(function patchElementalScanner(attempt){"
                + "if(window.__elementalNativeScannerInstalled){return;}"
                + "if(!window.Html5Qrcode||!window.ElementalAndroid){"
                + "if(attempt<50){setTimeout(function(){patchElementalScanner(attempt+1);},100);}return;}"
                + "window.__elementalNativeScannerInstalled=true;"
                + "window.Html5Qrcode.prototype.start=function(camera,config,onSuccess,onError){"
                + "window.__elementalNativeScanSuccess=onSuccess;"
                + "window.__elementalNativeScanError=onError;"
                + "window.ElementalAndroid.startScanner();return Promise.resolve();};"
                + "window.Html5Qrcode.prototype.stop=function(){"
                + "window.ElementalAndroid.stopScanner();return Promise.resolve();};"
                + "window.__elementalDeliverNativeScan=function(value){"
                + "if(typeof window.__elementalNativeScanSuccess==='function'){"
                + "window.__elementalNativeScanSuccess(value,{decodedText:value});}};"
                + "})(0);";
        webView.evaluateJavascript(script, null);
    }

    private final class ScannerBridge {
        @JavascriptInterface
        public void startScanner() {
            runOnUiThread(() -> {
                if (isCurrentPageTrusted()) {
                    requestNativeScanner();
                }
            });
        }

        @JavascriptInterface
        public void stopScanner() {
            runOnUiThread(() -> {
                if (isCurrentPageTrusted()) {
                    hideNativeScanner();
                }
            });
        }
    }

    private void requestNativeScanner() {
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            showNativeScanner();
            return;
        }
        nativeScannerPermissionPending = true;
        requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
    }

    private void showNativeScanner() {
        nativeScannerPermissionPending = false;
        nativeScanner.setVisibility(View.VISIBLE);
        closeScannerButton.setVisibility(View.VISIBLE);
        nativeScanner.resume();
    }

    private void hideNativeScanner() {
        nativeScannerPermissionPending = false;
        nativeScanner.pause();
        nativeScanner.setVisibility(View.GONE);
        closeScannerButton.setVisibility(View.GONE);
    }

    private void deliverNativeScan(String value) {
        if (value == null || value.isEmpty()) {
            return;
        }
        long now = SystemClock.elapsedRealtime();
        if (value.equals(lastNativeScan) && now - lastNativeScanAt < 1500) {
            return;
        }
        lastNativeScan = value;
        lastNativeScanAt = now;
        webView.evaluateJavascript(
                "window.__elementalDeliverNativeScan(" + JSONObject.quote(value) + ");",
                null
        );
    }

    private void handleWebPermissionRequest(PermissionRequest request) {
        boolean wantsOnlyCamera = Arrays.equals(
                request.getResources(),
                new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE}
        );
        if (!isTrustedOrigin(request.getOrigin()) || !wantsOnlyCamera) {
            request.deny();
            return;
        }
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            return;
        }
        pendingWebCameraRequest = request;
        requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != CAMERA_PERMISSION_REQUEST) {
            return;
        }
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (nativeScannerPermissionPending) {
            if (granted) {
                showNativeScanner();
            } else {
                nativeScannerPermissionPending = false;
            }
        }
        if (pendingWebCameraRequest != null) {
            PermissionRequest request = pendingWebCameraRequest;
            pendingWebCameraRequest = null;
            if (granted) {
                request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            } else {
                request.deny();
            }
        }
        if (!granted) {
            Toast.makeText(this, "Camera permission is required to scan QR codes.", Toast.LENGTH_LONG).show();
        }
    }

    private boolean openExternallyIfNeeded(Uri target) {
        if (isTrustedOrigin(target) || "about".equalsIgnoreCase(target.getScheme())) {
            return false;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, target));
        } catch (Exception error) {
            Toast.makeText(this, "Unable to open this link.", Toast.LENGTH_SHORT).show();
        }
        return true;
    }

    private boolean isTrustedOrigin(Uri target) {
        if (target == null || trustedOrigin == null) {
            return false;
        }
        return equalsIgnoreCase(trustedOrigin.getScheme(), target.getScheme())
                && equalsIgnoreCase(trustedOrigin.getHost(), target.getHost())
                && effectivePort(trustedOrigin) == effectivePort(target);
    }

    private boolean isCurrentPageTrusted() {
        String currentUrl = webView.getUrl();
        return currentUrl != null && isTrustedOrigin(Uri.parse(currentUrl));
    }

    private void updateGateScreenMode(Uri currentPage) {
        boolean isGateScreen = isTrustedOrigin(currentPage) && "/gate-scan".equals(currentPage.getPath());
        if (isGateScreen) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
    }

    private static boolean equalsIgnoreCase(String left, String right) {
        return left != null && right != null && left.equalsIgnoreCase(right);
    }

    private static int effectivePort(Uri uri) {
        if (uri.getPort() != -1) {
            return uri.getPort();
        }
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private static String joinUrl(String baseUrl, String path) {
        String base = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        String suffix = path.startsWith("/") ? path : "/" + path;
        return base + suffix;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (nativeScanner.getVisibility() == View.VISIBLE) {
            hideNativeScanner();
        } else if (setupPanel.getVisibility() == View.VISIBLE
                && getPreferences().contains(SITE_URL_KEY)) {
            showBrowser();
        } else if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        if (nativeScanner.getVisibility() == View.VISIBLE) {
            nativeScanner.pause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (nativeScanner.getVisibility() == View.VISIBLE
                && checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            nativeScanner.resume();
        }
    }

    @Override
    protected void onDestroy() {
        nativeScanner.pause();
        if (pendingWebCameraRequest != null) {
            pendingWebCameraRequest.deny();
            pendingWebCameraRequest = null;
        }
        webView.destroy();
        super.onDestroy();
    }
}
