---------------------------------------------------------------------------------------------------------------------------------------------------
**Table of Contents**

- [**Introduction**](#introduction)
- [**Setting Up A Local Build**](#setting-up-a-local-build)
- [**For Production**](#for-production)
  - [Frontend](#frontend)
  - [Backend](#backend)
    - [To test the dockerfile locally](#to-test-the-dockerfile-locally)
- [**Contributions**](#contributions)
- [**License**](#license)

---------------------------------------------------------------------------------------------------------------------------------------------------

## **Introduction**<a name="introduction"></a>
My personal portfolio, but better this time.

The personal portfolio and blog of Kaden Bilyeu (ktbilyeu), at https://kadenbilyeu.com.

Built with React, Vite, and Typescript

---------------------------------------------------------------------------------------------------------------------------------------------------

## **Setting Up A Local Build**<a name="setting-up-a-local-build"></a>

These steps must be followed _in order_.

1. Clone the repo, make sure you are using the correct branch (currently `production`)
2. Navigate to the `backend` directory. `cd backend`. Inside is the python backend.
3. Run the setup script with the local argument. This will install all requirements and setup the local env `python setup.py local`.
4. Run the server. For local `uvicorn main:app --reload --port 5000`
5. Open a new terminal and navigate to the `frontend` directory. `cd frontend`. Inside is the react (vite) frontend.
6. First install all required packages using `pnpm`. Run `pnpm install`. Then start the dev server with `pnpm dev`
7. Website will be on localhost:5173 (frontend) and localhost:5000 (backend)

Default login is admin:password

Also requires a totp code, default is JBSWY3DPEHPK3PXP so use that.

8. To serve the built site locally, use `pnpm preview` or simply `pnpm start` (alias).

--------------------------------------------------------------------------------------------------------------------------------------------------

## **For Production**<a name="for-production"></a>

### Frontend

Frontend is hosted on cloudflare pages. To deploy, push to the `production` branch. Development branch is for development only, intermediate builds deploy every commit.

### Backend

For production, the backend is hosted via a dockerfile.

The public origin defaults use `https://kadenbilyeu.com`. If an existing deployment
needs additional domains during a migration, configure them in its private runtime
environment before deploying:

- `CORS_ALLOWED_ORIGINS`: comma-separated exact browser origins, including the canonical origin.
- `CORS_PREVIEW_DOMAINS`: optional comma-separated Cloudflare project domains such as `project.pages.dev`; only one preview subdomain per configured project is accepted.
- `TERMINAL_ALLOWED_ORIGINS` and `DATABASE_RESTORE_ALLOWED_ORIGINS`: exact origins permitted to perform these authenticated admin operations.
- `WEBAUTHN_ALLOWED_ORIGINS`: exact production origins accepted for existing passkeys. The relying-party ID remains `kadenbilyeu.com`.

Do not commit a deployment's private environment file. `backend/runtime.env` is
ignored by Git. Origin lists replace defaults; an explicitly empty list permits no origins.

The sitemap uses the saved public `/site-settings` response. It lists only the home
page while minimal mode is enabled or settings are unavailable, and never recovers
hidden blog links from a previous sitemap. `SITEMAP_SETTINGS_API` and `SITEMAP_API`
can point to a test backend when building locally. A build does not change the saved setting.

#### To test the dockerfile locally
1. docker build -t kadenbilyeu.com -f build.dockerfile .
2. docker run -p 8000:8000 kadenbilyeu.com

---------------------------------------------------------------------------------------------------------------------------------------------------

## **Contributions**<a name="contributions"></a>

I welcome contributions to my site and corrections to any inaccuracies found on the site. Please feel free to fork the repository, make changes, and submit a pull request.

---------------------------------------------------------------------------------------------------------------------------------------------------

## **License**<a name="license"></a>

This site (kadenbilyeu.com) is licensed under the GNU Affero General Public License (AGPLv3). You can find the full text of the license in the [LICENSE](License.md) file.

The AGPLv3 is a copyleft license that promotes the principles of open-source software. It ensures that any derivative works based on this project, as well as any software that interacts with users over a network, must also be distributed under the same AGPLv3 license. This license grants you the freedom to use, modify, and distribute the software.

Please note that this information is a brief summary of the AGPLv3. For a detailed understanding of your rights and obligations under this license, please refer to the full license text.
