/**
 * Open a modal dialog with the given repository data
 * @param {Object} repo - Repository data to display in the modal
 */
function openModal(repo) {
    // Get modal elements
    const modal = document.getElementById('repoModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    
    if (!modal || !modalTitle || !modalBody) {
        console.error('Modal elements not found in the DOM');
        return;
    }
    
    // Set modal content based on repo data
    modalTitle.textContent = repo.full_name || 'Repository Details';
    
    // Build modal content
    let content = '';
    
    // Add repository image if available
    if (repo.owner && repo.owner.avatar_url) {
        content += `<img src="${repo.owner.avatar_url}" alt="${repo.owner.login}" class="avatar mb-3" style="width:60px;border-radius:50%">`;
    }
    
    // Add description
    content += `<p>${repo.description || 'No description available'}</p>`;
    
    // Add repository details
    content += '<div class="repo-details">';
    if (repo.language) content += `<span class="badge bg-primary me-2">${repo.language}</span>`;
    if (repo.stargazers_count !== undefined) content += `<span class="badge bg-warning me-2">★ ${repo.stargazers_count}</span>`;
    if (repo.forks_count !== undefined) content += `<span class="badge bg-info me-2">🍴 ${repo.forks_count}</span>`;
    content += '</div>';
    
    // Add links
    content += '<div class="mt-3">';
    if (repo.html_url) content += `<a href="${repo.html_url}" target="_blank" class="btn btn-primary me-2">View on GitHub</a>`;
    if (repo.id) content += `<a href="/repo/${repo.id}" class="btn btn-success">View Analysis</a>`;
    content += '</div>';
    
    modalBody.innerHTML = content;
    
    // Show the modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
}

/**
 * Close the currently open modal
 */
function closeModal() {
    const modal = document.getElementById('repoModal');
    if (modal) {
        const bootstrapModal = bootstrap.Modal.getInstance(modal);
        if (bootstrapModal) {
            bootstrapModal.hide();
        }
    }
}
