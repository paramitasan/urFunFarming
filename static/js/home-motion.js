// Home: the hero intro, then the tiles, profile card and band rise as they come into view
if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
    gsap.defaults({ ease: 'power2.out' });

    const mm = gsap.matchMedia();

    mm.add('(min-width: 0px)', () => {
        try {
            heroIntro(document.querySelector('.hero'));

            if (document.querySelector('.subnav')) {
                gsap.from('.subnav', { opacity: 0, y: -6, duration: 0.4, delay: 0.1 });
            }

            document.querySelectorAll('.launch-row').forEach((row) =>
                // clearProps drops GSAP's inline transform afterwards so the CSS hover lift still works
                gsap.from(row.querySelectorAll('.launch-tile'), {
                    y: 10, opacity: 0, duration: 0.45, stagger: 0.06,
                    clearProps: 'transform,translate,rotate,scale',
                    scrollTrigger: { trigger: row, start: 'top 90%', once: true }
                })
            );

            gsap.from('.home-profile, .role-band', {
                y: 10, opacity: 0, duration: 0.45, stagger: 0.1,
                scrollTrigger: { trigger: '.home-profile', start: 'top 90%', once: true }
            });
        } catch (error) {
            // Undo every set() so nothing stays hidden if setup breaks partway
            setTimeout(() => mm.revert());
        }
    });

    window.addEventListener('load', () => ScrollTrigger.refresh());
}
