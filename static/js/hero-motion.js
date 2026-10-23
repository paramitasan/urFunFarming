// Hero intro shared by the landing page and Home: sky, sun, buildings, clouds and the headline.
// Elements are hidden here, not in CSS, so the page shows normally if a script fails.
function heroIntro(hero) {
    const period = hero.dataset.period || 'afternoon';
    const has = (selector) => hero.querySelector(selector) ? hero.querySelectorAll(selector) : null;
    const intro = gsap.timeline();

    gsap.set('.hero .line', { clipPath: 'inset(0 0 100% 0)' });
    gsap.set('#skyline .bld', { scaleY: 0.96, opacity: 0, transformOrigin: '50% 100%' });
    gsap.set('.cloud', { opacity: 0, x: -15 });
    intro
        .to('.hero .line', { clipPath: 'inset(0 0 0% 0)', duration: 0.45, stagger: 0.06 }, 0)
        .to('#skyline .bld', { scaleY: 1, opacity: 1, duration: 0.7, stagger: { each: 0.05, from: 'center' } }, 0.1)
        .to('.cloud', { opacity: 1, x: 0, duration: 0.8, stagger: 0.08 }, 0.3);

    [['.sub', 0.1], ['.ctas', 0.15], ['.home-edit', 0.15]].forEach(([selector, at]) => {
        const nodes = has(selector);
        if (!nodes) return;
        gsap.set(nodes, { opacity: 0, y: 6 });
        intro.to(nodes, { opacity: 1, y: 0, duration: 0.4 }, at);
    });

    if (period === 'night') {
        gsap.set('.night-sky', { opacity: 0 });
        intro.to('.night-sky', { opacity: 1, duration: 1.2 }, 0.2);
    } else {
        gsap.set('.hero .sun', { y: '35vh' });
        gsap.set('.hero .glow', { opacity: 0 });
        intro
            .to('.hero .sun', { y: 0, duration: 1.4 }, 0)
            .to('.hero .glow', { opacity: 1, duration: 1.4 }, 0.1);
        // Only the plain afternoon sky warms up; the morning and evening gradients keep their colour
        if (period === 'afternoon') {
            gsap.set('.hero', { backgroundColor: '#FBEFD9' });
            intro.to('.hero', { backgroundColor: '#E6F0DC', duration: 1.6, ease: 'power2.inOut' }, 0);
        }
    }

    [['.c1', 20, 26], ['.c2', -18, 34], ['.c3', 14, 20]].forEach(([selector, dx, duration]) =>
        gsap.to(selector, { x: dx, duration, ease: 'none', repeat: -1, yoyo: true, delay: 2 })
    );
}
