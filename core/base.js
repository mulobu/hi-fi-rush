/* core/base.js -- page parameters, read first
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* Declared before anything else: the page's own config may read them. */
      const params = new URLSearchParams(location.search);
      const DEBUG = params.has("debug");
