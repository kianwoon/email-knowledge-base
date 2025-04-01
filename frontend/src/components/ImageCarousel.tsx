import React from 'react';
import { Box, IconButton, useColorMode } from '@chakra-ui/react';
import { ChevronLeftIcon, ChevronRightIcon } from '@chakra-ui/icons';
import Slider from 'react-slick';
import 'slick-carousel/slick/slick.css';
import 'slick-carousel/slick/slick-theme.css';

interface ImageCarouselProps {
  images: {
    src: string;
    alt: string;
  }[];
}

const ImageCarousel: React.FC<ImageCarouselProps> = ({ images }) => {
  const { colorMode } = useColorMode();
  const sliderRef = React.useRef<Slider>(null);

  const settings = {
    dots: true,
    infinite: true,
    speed: 500,
    slidesToShow: 1,
    slidesToScroll: 1,
    autoplay: true,
    autoplaySpeed: 5000,
    pauseOnHover: true,
    arrows: false,
  };

  const goToPrev = () => {
    if (sliderRef.current) {
      sliderRef.current.slickPrev();
    }
  };

  const goToNext = () => {
    if (sliderRef.current) {
      sliderRef.current.slickNext();
    }
  };

  return (
    <Box position="relative" width="100%" height="100%">
      <Slider ref={sliderRef} {...settings}>
        {images.map((image, index) => (
          <Box
            key={index}
            height={{ base: "250px", md: "500px" }}
            position="relative"
            overflow="hidden"
          >
            <Box
              as="img"
              src={image.src}
              alt={image.alt}
              objectFit="cover"
              height="100%"
              width="100%"
              sx={{
                clipPath: 'circle(40% at 50% 50%)',
                transform: { base: 'scale(1.2)', md: 'scale(1.5)' },
                margin: '0 auto',
                display: 'block',
                borderRadius: '50%'
              }}
            />
          </Box>
        ))}
      </Slider>

      <IconButton
        aria-label="Previous slide"
        icon={<ChevronLeftIcon />}
        position="absolute"
        left="0"
        top="50%"
        transform="translateY(-50%)"
        zIndex={2}
        onClick={goToPrev}
        bg={colorMode === 'dark' ? 'whiteAlpha.200' : 'blackAlpha.200'}
        _hover={{ bg: colorMode === 'dark' ? 'whiteAlpha.300' : 'blackAlpha.300' }}
        size="lg"
      />

      <IconButton
        aria-label="Next slide"
        icon={<ChevronRightIcon />}
        position="absolute"
        right="0"
        top="50%"
        transform="translateY(-50%)"
        zIndex={2}
        onClick={goToNext}
        bg={colorMode === 'dark' ? 'whiteAlpha.200' : 'blackAlpha.200'}
        _hover={{ bg: colorMode === 'dark' ? 'whiteAlpha.300' : 'blackAlpha.300' }}
        size="lg"
      />
    </Box>
  );
};

export default ImageCarousel; 