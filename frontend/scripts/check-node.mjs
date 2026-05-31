const major = Number(process.version.slice(1).split(".")[0]);

if (major < 18) {
  console.error(
    `\n❌ Node.js ${process.version} quá cũ — Next.js 15 cần Node >= 18.18.\n\n` +
      "Chạy trong thư mục frontend:\n" +
      "  nvm use\n" +
      "  npm run dev\n\n" +
      "Hoặc cài Node 20 LTS: nvm install 20 && nvm use 20\n",
  );
  process.exit(1);
}
